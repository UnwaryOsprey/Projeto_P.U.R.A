from pura.envfile import load_dotenv, parse_env_text


def test_parse_ignores_comments_and_handles_quotes():
    d = parse_env_text('# c\n\nA=1\nB = "dois"\nPURA_KEYS=sala=x,quarto=y\nC=3 # fim\nexport D=4\n')
    assert d == {"A": "1", "B": "dois", "PURA_KEYS": "sala=x,quarto=y", "C": "3", "D": "4"}


def test_load_handles_bom_crlf_and_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_bytes("\ufeffPURA_TESTE_A=um\r\nPURA_TESTE_B=dois\r\n".encode("utf-8"))
    monkeypatch.setenv("PURA_TESTE_B", "ambiente")
    monkeypatch.delenv("PURA_TESTE_A", raising=False)
    assert load_dotenv(f) == f
    import os
    assert os.environ["PURA_TESTE_A"] == "um"       # BOM nao vira parte do nome da variavel
    assert os.environ["PURA_TESTE_B"] == "ambiente"  # ambiente tem prioridade
    monkeypatch.delenv("PURA_TESTE_A", raising=False)
