# Painel público da COIPT-Sinop

Painel "COIPT em Números", hospedado gratuitamente no GitHub Pages em
**https://datawork10.github.io/coipt-sinop/**, com os dados atualizados
automaticamente a partir da planilha Google Sheets a cada 6 horas.

**Status: já configurado e no ar.** Repositório criado, `SHEET_ID` cadastrado
como Secret, GitHub Pages ativo, e a primeira execução automática já rodou com
sucesso. Não usa domínio próprio pago — o link do GitHub Pages é o endereço
definitivo do site.

## O que tem aqui

```
coipt-sinop/
├── index.html                    # a página (mesma do artifact do Claude)
├── data.json                     # dados atuais (sobrescrito automaticamente)
├── coipt-claro.png, coipt-escuro.png, dre-sinop.png, govmt.png   # logos
├── scripts/build_data.py         # busca a planilha e regenera data.json
└── .github/workflows/update-data.yml   # roda o script sozinho, de tempos em tempos
```

## Como a atualização automática funciona

- A cada 6 horas (ou quando você clicar em "Run workflow"), o GitHub Actions:
  1. Baixa as abas `raw_*` da sua planilha via exportação pública de CSV;
  2. Recalcula todos os indicadores **direto dos dados brutos** (não usa a
     aba "Apresente" — veja o porquê abaixo);
  3. Gera um novo `data.json`;
  4. Se algo mudou, publica automaticamente o site atualizado.
- Você não precisa fazer nada no dia a dia: é só continuar atualizando a
  planilha normalmente.

### Por que o script ignora a aba "Apresente"

A aba Apresente usa fórmulas de comparação exata (`COUNTIF` com texto fixo).
Isso já quebrou uma vez quando os status do inventário passaram a ter o
prefixo "FASE N - " — os indicadores voltaram a mostrar 0 sem ninguém notar
até a revisão manual. Para o painel público não repetir esse problema, o
script recalcula tudo direto das abas brutas usando comparação por trecho
(ex.: contém "tramitado npm"), que continua funcionando mesmo se o texto do
status mudar ligeiramente. Vale considerar aplicar o mesmo tipo de fórmula
(`COUNTIF(intervalo,"*texto*")`) na aba Apresente, já que o Looker Studio
interno lê essa aba e pode estar com os mesmos indicadores zerados.

### Ajustar a frequência de atualização

Edite a linha `cron` em `.github/workflows/update-data.yml`. Exemplos:
- `"0 */6 * * *"` — a cada 6 horas (padrão deste pacote)
- `"0 6,18 * * *"` — duas vezes por dia (6h e 18h UTC)
- `"0 * * * *"` — a cada hora

### Se um novo município aparecer sem acentuação correta

O script tem uma tabela `MUNICIPIO_FIX` no topo de `scripts/build_data.py`
para corrigir nomes de município que vêm em maiúsculas/sem acento nas abas
brutas (ex.: `CLAUDIA` → `Cláudia`). Se uma escola de um município novo for
cadastrada, adicione uma linha nessa tabela para manter a exibição correta;
caso contrário, o nome aparecerá em formato "Título Simples" sem acentos
especiais.

## Segurança

O site é 100% estático (HTML + JSON), sem backend e sem formulário de dados —
não há como alguém alterar as informações a partir da própria página. O único
ponto de atenção é o compartilhamento da planilha: mantenha-a como "somente
leitura" para quem tiver o link, e edite os dados apenas por dentro do Google
Sheets, como já é feito hoje.
