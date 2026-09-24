#!/usr/bin/env python3
"""Piloto sintético, uma configuração por execução; credenciais só em memória/tmpfs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HOME = Path('/home/rafael-moura')
MODELS = {
    'opus': ('claude-opus-5-5', 'high'),
    'muse': ('opencode/muse-spark-1.3-contributor-free', 'xhigh'),
    'mimo': ('opencode/mimo-v2.6-flash-free', None),  # catálogo sem variantes de esforço
    'sol': ('gpt-6-sol', 'high'),
}
HOSTS = {
    'opus': ['api.anthropic.com', 'claude.ai', 'platform.claude.com'],
    'muse': ['opencode.ai', 'models.opencode.ai', 'models.dev', 'registry.npmjs.org'],
    'mimo': ['opencode.ai', 'models.opencode.ai', 'models.dev', 'registry.npmjs.org'],
    'sol': ['chatgpt.com', 'api.openai.com', 'auth.openai.com'],
}


def docker(*args, input=None, timeout=60, check=True):
    result = subprocess.run(['docker', *args], input=input, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'Docker {args[0]} falhou ({result.returncode}): {result.stderr[:1500]}')
    return result


BOOTSTRAP = r'''
import json,sys,os
from pathlib import Path
payload=json.load(sys.stdin)
home=Path('/home/agent')
assert not list(home.iterdir()), 'Home não começou vazio'
assert not list(Path('/workspace').iterdir()), 'Workspace não começou vazio'
assert not Path('/home/rafael-moura').exists()
assert not Path('/var/run/docker.sock').exists()
for rel,value in payload['files'].items():
 p=home/rel;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(value));p.chmod(0o600)
Path('/workspace/input.txt').write_text(payload['input'])
print(json.dumps({'home_initially_empty':True,'workspace_initially_empty':True,'host_home_absent':True,'docker_socket_absent':True,'uid':os.getuid(),'home_env':os.environ.get('HOME'),'credential_paths':list(payload['credential_paths'])}))
'''

NETWORK_CHECK = r'''
import urllib.request, urllib.error, socket, json, os
results={}
try:
 urllib.request.urlopen('https://example.com',timeout=10)
 results['unlisted_host_blocked']=False
except urllib.error.URLError as e:
 results['unlisted_host_blocked']='403' in str(e)
try:
 s=socket.create_connection(('1.1.1.1',443),timeout=3);s.close()
 results['direct_egress_blocked']=False
except OSError: results['direct_egress_blocked']=True
print(json.dumps(results))
assert all(results.values()), 'Política básica de rede não passou'
'''

ARTIFACT_CHECK = r'''
import json,hashlib,sys
from pathlib import Path
original=sys.stdin.read().encode()
p=Path('/workspace/result.txt');src=Path('/workspace/input.txt')
regular=p.is_file() and not p.is_symlink()
data=p.read_bytes() if regular and p.stat().st_size<4096 else b''
print(json.dumps({'exists':regular,'matches_expected':regular and data==original.upper(),'original_input_unchanged':not src.is_symlink() and src.read_bytes()==original,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}))
'''


def credentials(participant):
    if participant == 'opus':
        data = json.loads((SOURCE_HOME/'.claude/.credentials.json').read_text())
        return {'.claude/.credentials.json': {'claudeAiOauth': data['claudeAiOauth']}}
    if participant == 'sol':
        data = json.loads((SOURCE_HOME/'.codex/auth.json').read_text())
        return {'.codex/auth.json': {k: data[k] for k in ('auth_mode', 'tokens', 'last_refresh', 'OPENAI_API_KEY') if k in data}}
    return {}


def sensitive_values(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from sensitive_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from sensitive_values(nested)
    elif isinstance(value, str) and len(value) > 24:
        yield value


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def usage_from_events(participant, events):
    """Consumo informado pelo próprio harness; None quando não observável.

    Os campos preservam a semântica de cada fonte, que não é equivalente entre
    ferramentas: veja 'source' e 'input_includes_cache'. Ausência não vira zero.
    """
    def num(value):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    def add(total, key, value):
        value = num(value)
        if value is not None:
            total[key] = (total.get(key) or 0) + value

    fields = ('input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens', 'cache_write_tokens', 'reported_cost_usd')
    usage = dict.fromkeys(fields)
    events = [e for e in events if isinstance(e, dict)]
    if participant == 'opus':
        results = [e for e in events if e.get('type') == 'result']
        if not results:
            return None
        result = results[-1]
        raw = result.get('usage') if isinstance(result.get('usage'), dict) else {}
        usage.update(input_tokens=num(raw.get('input_tokens')), output_tokens=num(raw.get('output_tokens')),
                     cache_read_tokens=num(raw.get('cache_read_input_tokens')),
                     cache_write_tokens=num(raw.get('cache_creation_input_tokens')),
                     reported_cost_usd=num(result.get('total_cost_usd')))
        by_model = result.get('modelUsage') if isinstance(result.get('modelUsage'), dict) else {}
        limits = ('contextWindow', 'maxOutputTokens')  # capacidade do modelo, não consumo
        usage['by_model'] = {name: {k: v for k, v in data.items() if num(v) is not None and k not in limits}
                             for name, data in by_model.items() if isinstance(data, dict)}
        for data in usage['by_model'].values():
            add(usage, 'reasoning_tokens', data.get('thinkingTokens'))
        usage.update(source='claude stream-json: último evento result; raciocínio de modelUsage.thinkingTokens',
                     input_includes_cache=False, events=len(results))
    elif participant in ('muse', 'mimo'):
        steps = [e.get('part') for e in events if e.get('type') == 'step_finish' and isinstance(e.get('part'), dict)]
        steps = [p for p in steps if isinstance(p.get('tokens'), dict)]
        if not steps:
            return None
        for part in steps:
            tokens = part['tokens']
            cache = tokens.get('cache') if isinstance(tokens.get('cache'), dict) else {}
            add(usage, 'input_tokens', tokens.get('input'))
            add(usage, 'output_tokens', tokens.get('output'))
            add(usage, 'reasoning_tokens', tokens.get('reasoning'))
            add(usage, 'cache_read_tokens', cache.get('read'))
            add(usage, 'cache_write_tokens', cache.get('write'))
            add(usage, 'reported_cost_usd', part.get('cost'))
        usage.update(source='opencode json: soma dos eventos step_finish', input_includes_cache=None, events=len(steps))
    else:
        turns = [e.get('usage') for e in events if e.get('type') == 'turn.completed' and isinstance(e.get('usage'), dict)]
        if not turns:
            return None
        for raw in turns:
            add(usage, 'input_tokens', raw.get('input_tokens'))
            add(usage, 'output_tokens', raw.get('output_tokens'))
            add(usage, 'reasoning_tokens', raw.get('reasoning_output_tokens'))
            add(usage, 'cache_read_tokens', raw.get('cached_input_tokens'))
        usage.update(source='codex exec --json: soma dos eventos turn.completed', input_includes_cache=True, events=len(turns))
    return usage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('participant', choices=MODELS)
    parser.add_argument('--image', default='llm-bench-pilot:20260924')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not 15 <= args.timeout <= 600:
        parser.error('timeout deve estar entre 15 e 600 segundos')
    model, effort = MODELS[args.participant]
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+args.participant+'-'+secrets.token_hex(3)
    output = ROOT/'.pilot/runs'/run_id
    output.mkdir(parents=True, mode=0o700)
    internal, proxy, agent = [f'llmbench-{run_id}-{suffix}' for suffix in ('net','proxy','agent')]
    auth = credentials(args.participant)
    redact_values = list(sensitive_values(auth))

    def redact(text):
        for value in redact_values:
            text = text.replace(value, '[REDACTED]')
        return text

    summary = {'run_id': run_id, 'participant': args.participant, 'requested_model': model,
               'effort': effort, 'timeout_seconds': args.timeout, 'skills': [],
               'allowed_hosts': HOSTS[args.participant], 'official_collection': False,
               'started_at_utc': utc_now()}
    started = time.monotonic()
    try:
        info = json.loads(docker('image','inspect',args.image).stdout)[0]
        summary['image_id'] = info['Id']
        docker('network','create','--internal',internal)
        common = ['--init','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                  '--pids-limit','256','--tmpfs','/tmp:rw,nosuid,nodev,size=512m',
                  '--tmpfs','/home/agent:rw,nosuid,nodev,uid=1001,gid=1001,mode=700,size=512m',
                  '--tmpfs','/workspace:rw,nosuid,nodev,uid=1001,gid=1001,mode=700,size=512m']
        docker('run','-d','--name',proxy,*common,'--memory','256m','--cpus','1',
               '--env','PILOT_ALLOWED_HOSTS='+','.join(HOSTS[args.participant]),
               args.image,'python3','/opt/pilot/proxy.py')
        docker('network','connect','--alias','pilot-proxy',internal,proxy)
        env = ['--env','HTTPS_PROXY=http://pilot-proxy:8080','--env','HTTP_PROXY=http://pilot-proxy:8080',
               '--env','https_proxy=http://pilot-proxy:8080','--env','http_proxy=http://pilot-proxy:8080',
               '--env','NO_PROXY=localhost,127.0.0.1','--env','DISABLE_AUTOUPDATER=1',
               '--env','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1']
        docker('run','-d','--name',agent,*common,'--network',internal,'--memory','2g','--cpus','2',*env,args.image)
        files = dict(auth)
        if args.participant == 'opus':
            files['.claude.json'] = {'hasCompletedOnboarding': True}
            files['.claude/settings.json'] = {'autoMemoryEnabled': False}
        elif args.participant in ('muse','mimo'):
            files['.config/opencode/opencode.json'] = {
                'autoupdate':False, 'share':'disabled', 'model':model,
                'enabled_providers':[model.split('/')[0]],
                'permission':{'*':'deny','bash':'allow','read':'allow','edit':'allow','glob':'allow','grep':'allow'},
            }
        payload={'files':files,'credential_paths':list(auth),'input':'trial '+secrets.token_hex(12)+'\n'}
        summary['preflight']=json.loads(docker('exec','-i',agent,'python3','-c',BOOTSTRAP,input=json.dumps(payload)).stdout)
        summary['network']=json.loads(docker('exec',agent,'python3','-c',NETWORK_CHECK).stdout)
        prompt = ('Piloto sintético de infraestrutura. Sua única tarefa: leia /workspace/input.txt, '
                  'grave seu conteúdo em letras maiúsculas ASCII em /workspace/result.txt, preservando a quebra de linha, '
                  'e execute um comando Python que confira a igualdade com o conteúdo original convertido. '
                  'Trabalhe apenas em /workspace. Não leia credenciais, não acesse a rede, não use subagentes '
                  'nem instale pacotes. Ao terminar, responda apenas PILOT_OK.')
        if args.participant == 'opus':
            cmd=['claude','-p',prompt,'--model',model,'--effort',effort,'--output-format','stream-json',
                 '--verbose','--no-session-persistence','--permission-mode','dontAsk',
                 '--tools','Bash,Read,Write,Edit','--allowedTools','Bash,Read,Write,Edit',
                 '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-chrome']
        elif args.participant in ('muse','mimo'):
            variant=['--variant',effort] if effort else []
            cmd=['opencode','--pure','run','--model',model,*variant,'--format','json',prompt]
        else:
            cmd=['codex','--no-daemon','-a','never','exec','--ignore-user-config','--ignore-rules',
                 '--model',model,'-c','model_reasoning_effort="high"','--sandbox','danger-full-access',
                 '--skip-git-repo-check','--ephemeral','--json',prompt]
        summary['command']=cmd
        task_start=time.monotonic()
        summary['task_started_at_utc']=utc_now()
        try:
            result=docker('exec',agent,'timeout','--signal=TERM','--kill-after=10s',str(args.timeout),*cmd,timeout=args.timeout+20,check=False)
            stdout,stderr=result.stdout,result.stderr
            summary['exit_code']=result.returncode
            summary['timed_out']=result.returncode in (124,137)
        except subprocess.TimeoutExpired as e:
            stdout=e.stdout or b'';stderr=e.stderr or b''
            stdout=stdout.decode(errors='replace') if isinstance(stdout,bytes) else stdout
            stderr=stderr.decode(errors='replace') if isinstance(stderr,bytes) else stderr
            summary['timed_out']=True;summary['exit_code']=None
            docker('exec',agent,'pkill','-TERM','-u','1001',check=False)
        summary['task_seconds']=round(time.monotonic()-task_start,3)
        (output/'stdout.jsonl').write_text(redact(stdout))
        (output/'stderr.txt').write_text(redact(stderr))
        summary['artifact']=json.loads(docker('exec','-i',agent,'python3','-c',ARTIFACT_CHECK,input=payload['input']).stdout)
        if summary['artifact']['matches_expected']:
            (output/'result.txt').write_text(payload['input'].upper())
        reported=set()
        variants=set()
        sessions=set()
        events=[]
        def walk(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('model','modelID') and isinstance(v,str): reported.add(v)
                    if k=='variant' and isinstance(v,str): variants.add(v)
                    if k=='modelUsage' and isinstance(v,dict): reported.update(v)
                    walk(v)
            elif isinstance(value,list):
                for v in value: walk(v)
        for line in stdout.splitlines():
            try:
                event=json.loads(line)
                events.append(event)
                walk(event)
                if isinstance(event,dict) and isinstance(event.get('sessionID'),str):
                    sessions.add(event['sessionID'])
            except ValueError: pass
        if args.participant in ('muse','mimo') and len(sessions)==1:
            exported=docker('exec',agent,'opencode','--pure','export',next(iter(sessions)),check=False)
            try:
                session=json.loads(exported.stdout)
                (output/'session.json').write_text(redact(exported.stdout))
                walk(session)
                summary['session_exported']=True
            except ValueError:
                summary['session_exported']=False
        summary['reported_models']=sorted(reported)
        summary['reported_variants']=sorted(variants)
        try:
            summary['usage']=usage_from_events(args.participant,events)
        except Exception as e:
            summary['usage']=None
            summary['usage_error']=redact(str(e))
        summary['passed']=(summary.get('exit_code')==0 and summary['artifact']['matches_expected'] and summary['artifact']['original_input_unchanged'])
        summary['pilot_ok_reported']='PILOT_OK' in stdout
    except Exception as e:
        summary['passed']=False
        summary['error']=redact(str(e))
    finally:
        summary['total_seconds']=round(time.monotonic()-started,3)
        summary['finished_at_utc']=utc_now()
        logs=docker('logs',proxy,check=False)
        (output/'proxy.log').write_text(redact(logs.stdout+logs.stderr))
        cleanup=[]
        for name in (agent,proxy):
            cleanup.append(docker('rm','-f',name,check=False).returncode)
        cleanup.append(docker('network','rm',internal,check=False).returncode)
        summary['cleanup_exit_codes']=cleanup
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Evidências locais:',output)
    return 0 if summary.get('passed') else 1


if __name__=='__main__':
    raise SystemExit(main())
