# Painel público da COIPT-Sinop

Este pacote publica o painel "COIPT em Números" em `coipt-sinop.app`, hospedado
gratuitamente no GitHub Pages, com os dados atualizados automaticamente a
partir da sua planilha Google Sheets a cada 6 horas.

## O que tem aqui

```
coipt-sinop/
├── index.html                    # a página (mesma do artifact do Claude)
├── data.json                     # dados atuais (será sobrescrito automaticamente)
├── coipt-claro.png, coipt-escuro.png, dre-sinop.png, govmt.png   # logos
├── CNAME                         # diz ao GitHub Pages qual domínio usar
├── scripts/build_data.py         # busca a planilha e regenera data.json
└── .github/workflows/update-data.yml   # roda o script sozinho, de tempos em tempos
```

## Passo 1 — Criar o repositório no GitHub

1. Crie uma conta no GitHub, se ainda não tiver: https://github.com/signup
2. Clique em "New repository". Nome sugerido: `coipt-sinop`. Marque como **público**
   (o GitHub Pages gratuito exige repositório público, a não ser que você tenha
   um plano GitHub pago).
3. Não inicialize com README (você vai enviar estes arquivos prontos).
4. Faça upload de todos os arquivos desta pasta mantendo a estrutura de pastas
   (o GitHub permite arrastar e soltar arquivos e pastas na tela do repositório,
   ou use `git push` se preferir a linha de comando).

## Passo 2 — Guardar o ID da planilha como "Secret"

O script busca os dados direto da sua planilha pública. Para isso ele precisa
saber o ID dela (o trecho da URL entre `/d/` e `/edit`):

```
https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/edit
```

No repositório do GitHub:
1. Vá em **Settings → Secrets and variables → Actions**.
2. Clique em **New repository secret**.
3. Nome: `SHEET_ID`
4. Valor: o ID copiado da URL da sua planilha.
5. Salve.

**Importante sobre a planilha:** ela precisa continuar compartilhada como
"Qualquer pessoa com o link pode **visualizar**" (a mesma configuração que já
está sendo usada hoje). O script lê os dados pela exportação pública de CSV do
Google Sheets — não precisa de senha nem de chave de API, mas também não
funciona se a planilha ficar restrita.

## Passo 3 — Ativar o GitHub Pages

1. No repositório, vá em **Settings → Pages**.
2. Em "Build and deployment" → "Source", selecione **GitHub Actions**
   (não "Deploy from a branch").
3. Pronto — o workflow em `.github/workflows/update-data.yml` cuida do resto.

## Passo 4 — Rodar pela primeira vez

1. Vá na aba **Actions** do repositório.
2. Clique no workflow "Atualizar dados da COIPT e publicar no GitHub Pages".
3. Clique em **Run workflow** (botão à direita) para disparar manualmente a
   primeira execução, em vez de esperar pelo horário agendado.
4. Acompanhe o log. Se tudo correr bem, ao final ele mostra o link do site
   publicado (algo como `https://SEU-USUARIO.github.io/coipt-sinop/`).
5. Confira se o `data.json` foi commitado com números corretos antes de seguir
   para o domínio próprio.

## Passo 5 — Apontar o domínio coipt-sinop.app

Isso é feito onde você registrou o domínio `.app` (Google Domains, Registro.br,
GoDaddy, etc. — domínios `.app` **exigem HTTPS**, e o GitHub Pages já fornece
isso automaticamente).

1. No painel de DNS do seu domínio, crie estes registros:

   | Tipo  | Nome/Host | Valor |
   |-------|-----------|-------|
   | A     | @         | 185.199.108.153 |
   | A     | @         | 185.199.109.153 |
   | A     | @         | 185.199.110.153 |
   | A     | @         | 185.199.111.153 |
   | CNAME | www       | SEU-USUARIO.github.io |

2. Volte em **Settings → Pages** no GitHub e, em "Custom domain", digite
   `coipt-sinop.app` e salve (isso confirma o arquivo `CNAME` que já está no
   repositório).
3. Aguarde a propagação de DNS (de minutos a algumas horas) e marque a opção
   **Enforce HTTPS** assim que ela ficar disponível.

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
