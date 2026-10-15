import csv
import gzip
import json
from datetime import date

import pytest

from lab03.metricas.corretiva import (
    VERSOES,
    Versao,
    cfr_entrega,
    eh_corretiva,
    so_patch,
    versao,
)
from lab03.validacao import avaliar_heuristica


def release(tag, publicada, *mensagens, notas=""):
    return {
        "tag_name": tag,
        "published_at": publicada,
        "commits": [{"sha": str(i), "data": publicada, "mensagem": m} for i, m in enumerate(mensagens)],
        "body": notas,
    }


@pytest.mark.parametrize(
    "tag, esperado",
    [
        ("v2.3.1", Versao("", (2, 3, 1))),
        ("2.3.1", Versao("", (2, 3, 1))),
        ("release-2.3.1", Versao("", (2, 3, 1))),
        ("pacote@2.3.1", Versao("pacote", (2, 3, 1))),
        ("@novu/js@v3.7.1", Versao("@novu/js", (3, 7, 1))),
        ("rust-v0.0.17", Versao("rust", (0, 0, 17))),
        ("curl-8_17_0", Versao("curl", (8, 17, 0))),
        ("v1.89", Versao("", (1, 89, 0))),
        ("v3.20.19-lts", Versao("", (3, 20, 19))),
        ("ODP", None),
        ("nightly", None),
    ],
)
def test_versao_de_varios_formatos_de_tag(tag, esperado):
    assert versao(tag) == esperado


def test_so_patch_compara_so_o_mesmo_pacote():
    assert so_patch(release("pacote@2.3.1", ""), release("pacote@2.3.0", ""))
    assert not so_patch(release("pacote@2.4.0", ""), release("pacote@2.3.0", ""))
    assert so_patch(release("a@2.3.1", ""), release("b@2.3.0", "")) is None
    assert so_patch(release("nightly", ""), release("v2.3.0", "")) is None
    assert so_patch(release("v2.3.1", ""), None) is None


def test_exemplo_do_enunciado():
    releases = [
        release("v2.3.0", "2025-05-10T12:00:00Z"),
        release("v2.3.1", "2025-05-12T12:00:00Z", "fix: crash ao abrir arquivo"),
        release("v2.4.0", "2025-06-01T12:00:00Z", "feat: exportar PDF"),
        release("v2.5.0", "2025-06-20T12:00:00Z", "feat: modo escuro"),
    ]

    cfr = cfr_entrega(releases, "2025-12-31")

    # v2.3.0 falhou; v2.3.1 e v2.4.0 não (a seguinte não é corretiva ou sai depois de 7 dias);
    # v2.5.0 não tem seguinte
    assert (cfr.avaliadas, cfr.falharam, cfr.censuradas) == (4, 1, 0)
    assert cfr.taxa == pytest.approx(1 / 4)


def test_release_nos_ultimos_7_dias_da_janela_e_censurada():
    releases = [
        release("v1.0.0", "2025-12-20T00:00:00Z"),
        release("v1.0.1", "2025-12-25T00:00:00Z", "fix: regressão"),
        release("v1.0.2", "2025-12-31T23:00:00Z", "fix: outra"),
    ]

    cfr = cfr_entrega(releases, date(2025, 12, 31))

    # v1.0.0 + 7 dias = 27/12, dentro da janela; as outras duas ainda podiam ganhar correção
    assert (cfr.avaliadas, cfr.falharam, cfr.censuradas) == (1, 1, 2)
    assert cfr.taxa == 1


def test_so_censuradas_da_taxa_vazia():
    cfr = cfr_entrega([release("v1.0.0", "2025-12-30T00:00:00Z")], "2025-12-31")

    assert cfr.taxa is None
    assert (cfr.avaliadas, cfr.censuradas) == (0, 1)


def test_tag_de_monorepo():
    anterior = release("pacote@2.3.0", "2025-05-10T00:00:00Z")
    correcao = release("pacote@2.3.1", "2025-05-12T00:00:00Z", "fix(pacote): import quebrado",
                       notas="### Bug Fixes\n- import quebrado")

    assert eh_corretiva(correcao, anterior)
    assert cfr_entrega([anterior, correcao], "2025-12-31").falharam == 1


def test_tag_que_nao_e_semver_fica_com_as_mensagens():
    anterior = release("nightly-a", "2025-05-10T00:00:00Z")
    com_fix = release("nightly-b", "2025-05-11T00:00:00Z", "fix: crash")
    sem_fix = release("nightly-c", "2025-05-12T00:00:00Z", "feat: algo")

    for nome, regra in VERSOES.items():
        assert regra.decidir(com_fix, anterior), nome
        assert not regra.decidir(sem_fix, anterior), nome


def test_notas_com_mais_novidade_que_correcao_nao_sao_corretivas():
    anterior = release("v2.3.0", "2025-05-10T00:00:00Z")
    rotina = release("v2.3.1", "2025-05-12T00:00:00Z", "fix: a",
                     notas="## Features\n- add export\n- new theme\n## Bug fixes\n- crash")

    assert VERSOES["v3"].decidir(rotina, anterior)
    assert not eh_corretiva(rotina, anterior)


def test_v1_marca_qualquer_release_com_commit_de_fix():
    anterior = release("v2.3.0", "2025-05-10T00:00:00Z")
    minor = release("v2.4.0", "2025-05-12T00:00:00Z", "feat: a", "Revert \"feat: b\"")

    assert VERSOES["v1"].decidir(minor, anterior)
    assert not VERSOES["v2"].decidir(minor, anterior)


def test_avaliacao_contra_o_consenso(tmp_path):
    entrada = [
        {"repo": "o/r", "tag_name": "v1.0.1", "published_at": "2025-05-12T00:00:00Z",
         "notas": "Bug fixes", "anterior": {"tag_name": "v1.0.0", "published_at": "2025-05-10T00:00:00Z"},
         "commits": [{"sha": "a", "data": "2025-05-11T00:00:00Z", "mensagem": "fix: a"}]},
        {"repo": "o/r", "tag_name": "v1.1.0", "published_at": "2025-06-12T00:00:00Z",
         "notas": "New feature", "anterior": {"tag_name": "v1.0.1", "published_at": "2025-05-12T00:00:00Z"},
         "commits": [{"sha": "b", "data": "2025-06-11T00:00:00Z", "mensagem": "feat: b"},
                     {"sha": "c", "data": "2025-06-11T00:00:00Z", "mensagem": "fix: typo"}]},
    ]
    with gzip.open(tmp_path / avaliar_heuristica.ENTRADA, "wt", encoding="utf-8") as arquivo:
        arquivo.writelines(json.dumps(linha) + "\n" for linha in entrada)
    with (tmp_path / avaliar_heuristica.CONSENSO).open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerows([("repo", "tag_name", "consenso_corretiva"),
                            ("o/r", "v1.0.1", "sim"), ("o/r", "v1.1.0", "nao")])

    resultados = {r["versao"]: r for r in avaliar_heuristica.executar(tmp_path)}

    assert set(resultados) == set(VERSOES)
    assert resultados["v4"]["f1"] == 1
    assert resultados["v1"]["precisao"] == pytest.approx(0.5)
    tabela = (tmp_path / avaliar_heuristica.SAIDA).read_text(encoding="utf-8")
    assert tabela.count("\n| v") == len(VERSOES)


def test_avaliacao_sem_consenso_para_com_mensagem(tmp_path):
    with pytest.raises(avaliar_heuristica.ErroAvaliacao, match="concordancia"):
        avaliar_heuristica.ler_consenso(tmp_path / avaliar_heuristica.CONSENSO)
