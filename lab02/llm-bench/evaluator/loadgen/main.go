// Gerador de carga do diagnóstico de latência (RNF11, M16), executado no container cliente.
//
// Só biblioteca padrão. Lê os parâmetros em JSON pela entrada padrão e imprime o resultado
// em JSON. Cada resposta é validada contra o contrato; a latência de respostas inválidas ou
// com erro de transporte não entra nos percentis e é contada à parte.
//
// Operações (Op):
//
//	seed      cria Requests links (sem medir) e devolve os códigos e as URLs
//	visits    GET /api/links/{code} de cada código (sem medir); devolve a soma de visits
//	redirect  GET /{code} sobre os links semeados; válido = 302 com Location igual à url
//	create    POST /api/links sem alias; válido = 201 com objeto JSON e code string
//
// Modos de medição (Mode), para redirect e create:
//
//	open    taxa fixa: a requisição i é agendada para t0 + i/Rate e a latência é contada a
//	        partir do instante agendado (sem coordinated omission). Até MaxInflight em voo;
//	        se o limite for atingido, o atraso também entra na latência.
//	closed  malha fechada: Concurrency workers em sequência por WarmupS+DurationS segundos,
//	        limitados a MaxRequests requisições no total.
//
// Em ambos, as requisições agendadas (open) ou iniciadas (closed) nos primeiros WarmupS
// segundos são descartadas.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

type params struct {
	Host        string   `json:"host"`
	Port        int      `json:"port"`
	Op          string   `json:"op"`
	Mode        string   `json:"mode"`
	Concurrency int      `json:"concurrency"`
	Rate        float64  `json:"rate"`
	WarmupS     float64  `json:"warmup_s"`
	DurationS   float64  `json:"duration_s"`
	MaxRequests int      `json:"max_requests"`
	MaxInflight int      `json:"max_inflight"`
	Requests    int      `json:"requests"`
	Codes       []string `json:"codes"`
	URLs        []string `json:"urls"`
	TimeoutMs   int      `json:"timeout_ms"`
	Tag         string   `json:"tag"`
}

type result struct {
	Op             string         `json:"op"`
	Mode           string         `json:"mode,omitempty"`
	Concurrency    int            `json:"concurrency,omitempty"`
	TargetRate     float64        `json:"target_rate,omitempty"`
	WarmupS        float64        `json:"warmup_s,omitempty"`
	DurationS      float64        `json:"duration_s,omitempty"`
	Sent           int            `json:"sent"`
	Measured       int            `json:"measured"`
	Valid          int            `json:"valid"`
	WarmupValid    int            `json:"warmup_valid"`
	Invalid        int            `json:"invalid"`
	TransportErr   int            `json:"transport_errors"`
	ErrorRate      float64        `json:"error_rate"`
	WallSeconds    float64        `json:"wall_seconds"`
	ThroughputRPS  float64        `json:"throughput_valid_rps"`
	CappedByMax    bool           `json:"capped_by_max_requests,omitempty"`
	LateStarts     int            `json:"late_starts_over_1ms,omitempty"`
	LatencyMs      map[string]any `json:"latency_ms,omitempty"`
	ServiceMs      map[string]any `json:"service_ms,omitempty"`
	StartLagMs     map[string]any `json:"start_lag_ms,omitempty"`
	Statuses       map[string]int `json:"statuses,omitempty"`
	InvalidSamples []string       `json:"invalid_samples,omitempty"`
	VisitsTotal    *int           `json:"visits_total,omitempty"`
	Codes          []string       `json:"codes,omitempty"`
	URLs           []string       `json:"urls,omitempty"`
}

type sample struct {
	start  time.Time // instante agendado (open) ou de início (closed)
	ns     int64     // do instante agendado ao fim da resposta
	svc    int64     // do envio real ao fim da resposta
	lag    int64     // do instante agendado ao envio real
	valid  bool
	status int
	note   string
	code   string
	visits int
	late   bool
}

func main() {
	var p params
	if err := json.NewDecoder(os.Stdin).Decode(&p); err != nil {
		fail("parâmetros inválidos: " + err.Error())
	}
	if (p.Op == "redirect" || p.Op == "visits") && (len(p.Codes) == 0 || len(p.Codes) != len(p.URLs)) {
		fail("redirect e visits exigem codes e urls do mesmo tamanho")
	}
	timeout := time.Duration(p.TimeoutMs) * time.Millisecond
	conns := max(p.Concurrency, p.MaxInflight, 8)
	transport := &http.Transport{
		DialContext:         (&net.Dialer{Timeout: timeout}).DialContext,
		MaxIdleConns:        conns * 2,
		MaxIdleConnsPerHost: conns * 2,
		DisableCompression:  true,
	}
	client := &http.Client{Transport: transport, Timeout: timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	base := "http://" + p.Host + ":" + strconv.Itoa(p.Port)

	var r result
	switch p.Op {
	case "seed", "visits":
		r = fixedCount(client, base, &p)
	case "redirect", "create":
		switch p.Mode {
		case "open":
			r = openLoop(client, base, &p)
		case "closed":
			r = closedLoop(client, base, &p)
		default:
			fail("mode deve ser open ou closed")
		}
	default:
		fail("operação desconhecida: " + p.Op)
	}
	transport.CloseIdleConnections()
	out, _ := json.Marshal(r)
	os.Stdout.Write(append(out, '\n'))
}

// fixedCount executa seed ou visits: número fixo de requisições, sem medição.
func fixedCount(client *http.Client, base string, p *params) result {
	n := p.Requests
	if p.Op == "visits" {
		n = len(p.Codes)
	}
	c := max(p.Concurrency, 1)
	samples := make([]sample, n)
	var next int64 = -1
	var wg sync.WaitGroup
	for w := 0; w < c; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				i := int(atomic.AddInt64(&next, 1))
				if i >= n {
					return
				}
				samples[i] = do(client, base, p, i, time.Now())
			}
		}()
	}
	wg.Wait()
	r := result{Op: p.Op, Sent: n}
	total := 0
	for i, s := range samples {
		if !s.valid {
			fail(fmt.Sprintf("%s %d falhou: %s", p.Op, i, s.note))
		}
		if p.Op == "seed" {
			r.Codes = append(r.Codes, s.code)
			r.URLs = append(r.URLs, seedURL(p.Tag, i))
		} else {
			total += s.visits
		}
	}
	if p.Op == "visits" {
		r.VisitsTotal = &total
	}
	return r
}

func openLoop(client *http.Client, base string, p *params) result {
	if p.Rate <= 0 || p.DurationS <= 0 {
		fail("open exige rate e duration_s > 0")
	}
	total := int(math.Round((p.WarmupS + p.DurationS) * p.Rate))
	inflight := make(chan struct{}, max(p.MaxInflight, 1))
	samples := make([]sample, total)
	interval := time.Duration(float64(time.Second) / p.Rate)
	var wg sync.WaitGroup
	t0 := time.Now().Add(50 * time.Millisecond)
	for i := 0; i < total; i++ {
		intended := t0.Add(time.Duration(i) * interval)
		// Dorme até perto do instante e espera ativamente o último trecho: time.Sleep tem
		// imprecisão da ordem de 1 ms, e o atraso do cliente entraria na latência.
		if d := time.Until(intended); d > 2*time.Millisecond {
			time.Sleep(d - 2*time.Millisecond)
		}
		for time.Now().Before(intended) {
			runtime.Gosched()
		}
		inflight <- struct{}{} // bloqueia se o limite de requisições em voo foi atingido
		wg.Add(1)
		go func(i int, intended time.Time) {
			defer wg.Done()
			defer func() { <-inflight }()
			late := time.Since(intended) > time.Millisecond
			s := do(client, base, p, i, intended) // latência a partir do instante agendado
			s.late = late
			samples[i] = s
		}(i, intended)
	}
	wg.Wait()
	warmupEnd := t0.Add(time.Duration(p.WarmupS * float64(time.Second)))
	r := summarizeRun(p, samples, warmupEnd, p.DurationS)
	r.TargetRate = p.Rate
	return r
}

func closedLoop(client *http.Client, base string, p *params) result {
	if p.Concurrency < 1 || p.DurationS <= 0 {
		fail("closed exige concurrency ≥ 1 e duration_s > 0")
	}
	t0 := time.Now()
	stop := t0.Add(time.Duration((p.WarmupS + p.DurationS) * float64(time.Second)))
	limit := int64(p.MaxRequests)
	if limit <= 0 {
		limit = math.MaxInt64
	}
	warmupEnd := t0.Add(time.Duration(p.WarmupS * float64(time.Second)))
	var next, measuredCount int64 = -1, 0
	var mu sync.Mutex
	var samples []sample
	var capped atomic.Bool
	var wg sync.WaitGroup
	for w := 0; w < p.Concurrency; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			local := make([]sample, 0, 4096)
			for {
				now := time.Now()
				if !now.Before(stop) {
					break
				}
				// O teto vale só para as requisições medidas; o aquecimento é limitado pelo tempo.
				if !now.Before(warmupEnd) && atomic.AddInt64(&measuredCount, 1) > limit {
					capped.Store(true)
					break
				}
				i := atomic.AddInt64(&next, 1)
				local = append(local, do(client, base, p, int(i), now))
			}
			mu.Lock()
			samples = append(samples, local...)
			mu.Unlock()
		}()
	}
	wg.Wait()
	measured := p.DurationS
	if capped.Load() { // janela efetiva: do fim do aquecimento à última resposta medida
		last := warmupEnd
		for _, s := range samples {
			if end := s.start.Add(time.Duration(s.ns)); end.After(last) {
				last = end
			}
		}
		measured = last.Sub(warmupEnd).Seconds()
	}
	r := summarizeRun(p, samples, warmupEnd, measured)
	r.Concurrency = p.Concurrency
	r.CappedByMax = capped.Load()
	return r
}

func summarizeRun(p *params, samples []sample, warmupEnd time.Time, window float64) result {
	r := result{Op: p.Op, Mode: p.Mode, WarmupS: p.WarmupS, DurationS: p.DurationS, Sent: len(samples),
		Statuses: map[string]int{}, InvalidSamples: []string{}}
	var lat, svc, lags []float64
	for _, s := range samples {
		if s.start.Before(warmupEnd) {
			if s.valid {
				r.WarmupValid++
			}
			continue
		}
		r.Measured++
		if s.late {
			r.LateStarts++
		}
		key := strconv.Itoa(s.status)
		if s.status == 0 {
			key = "sem resposta"
		}
		r.Statuses[key]++
		switch {
		case s.valid:
			r.Valid++
			lat = append(lat, float64(s.ns)/1e6)
		case s.status == 0:
			r.TransportErr++
		default:
			r.Invalid++
		}
		if !s.valid && len(r.InvalidSamples) < 5 {
			r.InvalidSamples = append(r.InvalidSamples, s.note)
		}
		if s.valid {
			svc = append(svc, float64(s.svc)/1e6)
			lags = append(lags, float64(s.lag)/1e6)
		}
	}
	r.WallSeconds = round(window, 3)
	if window > 0 {
		r.ThroughputRPS = round(float64(r.Valid)/window, 1)
	}
	if r.Measured > 0 {
		r.ErrorRate = round(float64(r.Invalid+r.TransportErr)/float64(r.Measured), 6)
	}
	r.LatencyMs = summarize(lat)
	if p.Mode == "open" { // em malha fechada, envio e início coincidem
		r.ServiceMs = summarize(svc)
		r.StartLagMs = summarize(lags)
	}
	return r
}

func seedURL(tag string, i int) string {
	return fmt.Sprintf("https://example.com/latencia/%s/%d?q=%d", tag, i, i)
}

func do(client *http.Client, base string, p *params, i int, start time.Time) sample {
	var req *http.Request
	var expectURL string
	switch p.Op {
	case "redirect":
		k := i % len(p.Codes)
		expectURL = p.URLs[k]
		req, _ = http.NewRequest("GET", base+"/"+p.Codes[k], nil)
	case "visits":
		req, _ = http.NewRequest("GET", base+"/api/links/"+p.Codes[i], nil)
	default: // create, seed
		url := fmt.Sprintf("https://example.com/latencia/%s/c%d", p.Tag, i)
		if p.Op == "seed" {
			url = seedURL(p.Tag, i)
		}
		body, _ := json.Marshal(map[string]string{"url": url})
		req, _ = http.NewRequest("POST", base+"/api/links", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	}
	sent := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		return sample{start: start, ns: time.Since(start).Nanoseconds(), svc: time.Since(sent).Nanoseconds(),
			lag: sent.Sub(start).Nanoseconds(), note: "transporte: " + shorten(err.Error())}
	}
	data, rerr := io.ReadAll(resp.Body)
	resp.Body.Close()
	end := time.Now()
	s := sample{start: start, ns: end.Sub(start).Nanoseconds(), svc: end.Sub(sent).Nanoseconds(),
		lag: sent.Sub(start).Nanoseconds(), status: resp.StatusCode}
	if rerr != nil {
		s.status, s.note = 0, "corpo: "+shorten(rerr.Error())
		return s
	}
	switch p.Op {
	case "redirect":
		loc := resp.Header.Get("Location")
		s.valid = resp.StatusCode == 302 && loc == expectURL
		if !s.valid {
			s.note = fmt.Sprintf("GET → %d, Location %q", resp.StatusCode, shorten(loc))
		}
	case "visits":
		var obj map[string]any
		if resp.StatusCode == 200 && json.Unmarshal(data, &obj) == nil {
			if v, ok := obj["visits"].(float64); ok {
				s.valid, s.visits = true, int(v)
			}
		}
		if !s.valid {
			s.note = fmt.Sprintf("GET /api/links → %d, corpo %q", resp.StatusCode, shorten(string(data)))
		}
	default:
		var obj map[string]any
		if resp.StatusCode == 201 && json.Unmarshal(data, &obj) == nil {
			if code, ok := obj["code"].(string); ok && code != "" {
				s.valid, s.code = true, code
			}
		}
		if !s.valid {
			s.note = fmt.Sprintf("POST → %d, corpo %q", resp.StatusCode, shorten(string(data)))
		}
	}
	return s
}

func summarize(lat []float64) map[string]any {
	if len(lat) == 0 {
		return nil
	}
	sort.Float64s(lat)
	sum := 0.0
	for _, v := range lat {
		sum += v
	}
	pct := func(q float64) float64 { // nearest-rank
		k := int(math.Ceil(q*float64(len(lat)))) - 1
		if k < 0 {
			k = 0
		}
		return round(lat[k], 3)
	}
	return map[string]any{"min": round(lat[0], 3), "p50": pct(0.50), "p90": pct(0.90), "p95": pct(0.95),
		"p99": pct(0.99), "p999": pct(0.999), "max": round(lat[len(lat)-1], 3), "mean": round(sum/float64(len(lat)), 3),
		"n": len(lat)}
}

func round(v float64, d int) float64 {
	m := math.Pow(10, float64(d))
	return math.Round(v*m) / m
}

func shorten(s string) string {
	if len(s) > 160 {
		return s[:160] + "…"
	}
	return s
}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(2)
}
