# Implementação de referência do encurtador

Controle positivo do avaliador (`evaluator/`), escrito em Python 3.11 só com biblioteca padrão e SQLite. Não é uma entrega de participante.

- Build: `./build.sh` (apenas compila `app.py`).
- Execução: `DATA_DIR=/caminho BASE_URL=http://localhost:8080 ./start.sh`; escuta em `0.0.0.0:8080`.
- Persistência: `DATA_DIR/links.sqlite3`. Links excluídos ficam marcados, para que o código não seja reutilizado.
- Testes: a verificação é o próprio avaliador; veja [docs/avaliador.md](../../docs/avaliador.md).
