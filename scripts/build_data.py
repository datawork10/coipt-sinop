#!/usr/bin/env python3
"""
Gera data.json para o painel público da COIPT-Sinop a partir da planilha
'Relação_produto_processo_COIPT' no Google Sheets.

Por que este script não lê a aba 'Apresente':
A aba Apresente usa fórmulas de comparação EXATA (COUNTIF com texto fixo).
Sempre que o vocabulário de status muda na planilha de origem (por exemplo,
quando um status passa a ter o prefixo "FASE N - ..."), essas fórmulas
silenciosamente voltam a contar 0 e ninguém percebe até alguém notar o
painel errado. Este script recalcula os indicadores direto das abas
'raw_*' usando comparação por trecho (substring/contains), o que é
resistente a esse tipo de mudança de vocabulário.

Uso:
    python3 build_data.py --sheet-id <ID_DA_PLANILHA> --out ../data.json

Não requer autenticação: a planilha precisa estar compartilhada como
"Qualquer pessoa com o link pode visualizar" (Leitor), pois os dados são
lidos via exportação pública de CSV (gviz).
"""
import argparse
import csv
import io
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

CSV_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet}"

# Correções de acentuação conhecidas para nomes de município que aparecem
# em maiúsculas/sem acento nas abas brutas. Se uma nova unidade escolar em
# um município ainda não mapeado aqui for cadastrada, adicione a forma
# correta abaixo (chave = maiúsculo sem acento).
MUNICIPIO_FIX = {
    "APIACAS": "Apiacás",
    "BOA ESPERANCA DO NORTE": "Boa Esperança do Norte",
    "CLAUDIA": "Cláudia",
    "COLIDER": "Colíder",
    "FELIZ NATAL": "Feliz Natal",
    "IPIRANGA DO NORTE": "Ipiranga do Norte",
    "ITANHANGA": "Itanhangá",
    "ITAUBA": "Itaúba",
    "LUCAS DO RIO VERDE": "Lucas do Rio Verde",
    "NOVA SANTA HELENA": "Nova Santa Helena",
    "NOVA UBIRATA": "Nova Ubiratã",
    "SANTA CARMEM": "Santa Carmem",
    "SINOP": "Sinop",
    "SORRISO": "Sorriso",
    "TABAPORA": "Tabaporã",
    "TAPURAH": "Tapurah",
    "UNIAO DO SUL": "União do Sul",
    "VERA": "Vera",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fix_municipio(raw):
    raw = clean(raw)
    if not raw:
        return raw
    key = strip_accents(raw).upper().strip()
    return MUNICIPIO_FIX.get(key, raw.strip().title())


# Correções de grafia conhecidas na aba "Organize" da planilha (erro na fonte,
# não no cálculo). Mantido aqui em vez de editar a planilha porque a lista de
# processos/produtos é digitada manualmente pela equipe e pode voltar a ter o
# mesmo erro numa edição futura; corrigir na leitura garante que o site
# publicado sempre mostre o texto certo, mesmo que a planilha ainda não tenha
# sido corrigida.
PROCESSO_FIX = {
    "Manutenção Corretivas nas Unidades Escolares": "Manutenções Corretivas nas Unidades Escolares",
}


def fix_processo(raw):
    return PROCESSO_FIX.get(raw, raw)


def clean(v):
    if v is None:
        return ""
    return str(v).strip()


def to_num(v, default=0.0):
    if v is None or v == "":
        return default
    s = str(v).strip()
    # A cell formatted as percentage exports from Google Sheets as literal
    # text like "25,00%", not as the underlying fraction (0.25) that
    # openpyxl would have given when reading the .xlsx directly. Detect the
    # "%" suffix and normalize back to a 0-1 fraction so downstream math
    # (which expects a fraction, matching the original AVERAGE() formula)
    # stays correct regardless of which path produced the number.
    is_percent = s.endswith("%")
    s = s.replace("R$", "").replace("%", "").replace(".", "").replace(",", ".").strip()
    try:
        n = float(s)
    except ValueError:
        try:
            n = float(v)
        except (TypeError, ValueError):
            return default
    return n / 100 if is_percent else n


def to_date(v):
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(v.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_sheet(sheet_id, sheet_name):
    url = CSV_URL.format(sheet_id=sheet_id, sheet=urllib.parse.quote(sheet_name))
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return [], []
    header = rows[0]
    body = rows[1:]
    return header, body


def col(rows, idx, default=""):
    out = []
    for r in rows:
        out.append(r[idx] if idx < len(r) else default)
    return out


def contains(value, needle):
    return needle.lower() in (value or "").lower()


def build(sheet_id):
    # ---------- raw tabs ----------
    _, conv_rows = fetch_sheet(sheet_id, "raw_convenios")
    _, inv_rows = fetch_sheet(sheet_id, "raw_inventarios")
    _, loc_rows = fetch_sheet(sheet_id, "raw_location")
    _, manut_rows = fetch_sheet(sheet_id, "raw_manut")
    _, chrome_rows = fetch_sheet(sheet_id, "raw_chromes")
    _, vigia_rows = fetch_sheet(sheet_id, "raw_vigia")
    _, dim_rows = fetch_sheet(sheet_id, "dim_unidades")
    _, org_rows = fetch_sheet(sheet_id, "Organize")
    _, meta_rows = fetch_sheet(sheet_id, "Metadados")

    today = datetime.now()

    # ---------- CONVÊNIOS ----------
    convenios = []
    for r in conv_rows:
        if not clean(r[0] if len(r) > 0 else ""):
            continue
        convenios.append({
            "n": clean(r[0]),
            "municipio": fix_municipio(r[1] if len(r) > 1 else ""),
            "escola": clean(r[2] if len(r) > 2 else ""),
            "objeto": clean(r[3] if len(r) > 3 else ""),
            "vigencia": clean(r[4] if len(r) > 4 else ""),
            "situacao": clean(r[5] if len(r) > 5 else ""),
            "execucao": round(to_num(r[6] if len(r) > 6 else 0) * 100, 4),
            "previsao": clean(r[7] if len(r) > 7 else ""),
        })
    conv_situacao = [c["vigencia"] for c in convenios]
    conv_obra = [c["situacao"] for c in convenios]
    conv_municipios = set(c["municipio"] for c in convenios if c["municipio"])
    conv_atualizadas_30d = 0
    for r in conv_rows:
        d = to_date(clean(r[9]) if len(r) > 9 else "")
        if d and d > today - timedelta(days=30):
            conv_atualizadas_30d += 1

    # ---------- INVENTÁRIO / PATRIMÔNIO ----------
    inventario = []
    for r in inv_rows:
        cod = clean(r[0] if len(r) > 0 else "")
        escola = clean(r[1] if len(r) > 1 else "")
        if not escola:
            continue
        inventario.append({
            "cod": cod,
            "escola": escola.upper(),
            "municipio": fix_municipio(r[2] if len(r) > 2 else ""),
            "nf": clean(r[3] if len(r) > 3 else ""),
            "mobiliario": clean(r[4] if len(r) > 4 else ""),
            "drive": clean(r[5] if len(r) > 5 else ""),
            "inservivel": clean(r[6] if len(r) > 6 else ""),
        })
    nf_col = col(inv_rows, 3)
    mob_col = col(inv_rows, 4)
    drive_col = col(inv_rows, 5)
    inserv_col = col(inv_rows, 6)
    h_col = col(inv_rows, 7)
    i_col = col(inv_rows, 8)
    total_inv = len(inventario)
    nf_enviadas = sum(1 for v in nf_col if contains(v, "enviado ao npm"))
    nf_paradas = sum(1 for v in nf_col if contains(v, "parado na escola"))
    mob_tramitado = sum(1 for v in mob_col if contains(v, "tramitado npm"))
    mob_devolvido = sum(1 for v in mob_col if contains(v, "devolvido para correção") or contains(v, "devolvido para correcao"))
    drive_enviado = sum(1 for v in drive_col if contains(v, "enviado para o drive"))
    inserv_tramitado = sum(1 for v in inserv_col if contains(v, "sigadoc tramitado"))
    inserv_nao_iniciado = sum(1 for v in inserv_col if contains(v, "não iniciado") or contains(v, "nao iniciado"))
    processos_abertos = sum(1 for v in h_col if contains(v, "seduc")) + sum(1 for v in i_col if contains(v, "seduc"))
    conclusao_mobiliario = round((mob_tramitado / total_inv * 100), 4) if total_inv else 0

    # ---------- LOCAÇÃO ----------
    locacao = []
    for r in loc_rows:
        escola = clean(r[0] if len(r) > 0 else "")
        if not escola:
            continue
        vig = to_date(clean(r[3]) if len(r) > 3 else "")
        pag = to_date(clean(r[4]) if len(r) > 4 else "")
        locacao.append({
            "escola": escola.upper(),
            "municipio": fix_municipio(r[1] if len(r) > 1 else ""),
            "processo": clean(r[2] if len(r) > 2 else ""),
            "vigencia": vig.strftime("%d/%m/%Y") if vig else clean(r[3] if len(r) > 3 else "") or "—",
            "ultimoPagamento": pag.strftime("%d/%m/%Y") if pag else clean(r[4] if len(r) > 4 else "") or "—",
            "tipo": clean(r[5] if len(r) > 5 else ""),
        })
    contratos_ativos = 0
    vigencias_90 = 0
    processos_instrucao = 0
    for r in loc_rows:
        vig = to_date(clean(r[3]) if len(r) > 3 else "")
        tipo = clean(r[5] if len(r) > 5 else "")
        # Igualdade exata com "Locação" (não "contém"): "Processo de locação
        # iniciado" também contém a palavra "locação", mas é uma etapa de
        # instrução, não um contrato ativo — contar por substring inflava
        # "Contratos de locação ativos" ao somar esse registro junto.
        is_locacao_ativa = tipo.strip().lower() == "locação" or tipo.strip().lower() == "locacao"
        if vig and vig > today and is_locacao_ativa:
            contratos_ativos += 1
            if vig <= today + timedelta(days=90):
                vigencias_90 += 1
        if contains(tipo, "iniciado"):
            processos_instrucao += 1

    # ---------- MANUTENÇÃO ----------
    manut_by_escola = defaultdict(lambda: {"total": 0, "aprovado": 0, "rejeitado": 0, "analisado": 0,
                                            "valorTotal": 0.0, "valorAprovado": 0.0})
    total_solic = aprov = rejeit = analis = 0
    valor_total = valor_aprovado = valor_rejeitado = valor_analisado = 0.0
    for r in manut_rows:
        unidade = clean(r[0] if len(r) > 0 else "")
        if not unidade:
            continue
        valor = to_num(r[3] if len(r) > 3 else 0)
        status = clean(r[4] if len(r) > 4 else "")
        key = unidade.upper()
        b = manut_by_escola[key]
        b["total"] += 1
        b["valorTotal"] += valor
        total_solic += 1
        valor_total += valor
        if status.lower() == "aprovado":
            b["aprovado"] += 1
            b["valorAprovado"] += valor
            aprov += 1
            valor_aprovado += valor
        elif status.lower() == "rejeitado":
            b["rejeitado"] += 1
            rejeit += 1
            valor_rejeitado += valor
        elif status.lower() == "analisado":
            b["analisado"] += 1
            analis += 1
            valor_analisado += valor
    manutencao = [{"escola": k, **v} for k, v in manut_by_escola.items()]
    manutencao.sort(key=lambda x: -x["total"])
    unidades_atendidas = len(manut_by_escola)
    taxa_aprovacao = round(aprov / (aprov + rejeit) * 100, 8) if (aprov + rejeit) else 0
    valor_medio = round(valor_total / total_solic, 5) if total_solic else 0
    media_por_unidade = round(total_solic / unidades_atendidas, 9) if unidades_atendidas else 0

    # ---------- TECNOLOGIA (Chromebooks) ----------
    chromebooks = []
    total_chrome = total_gabinetes = 0
    for r in chrome_rows:
        escola = clean(r[0] if len(r) > 0 else "")
        if not escola:
            continue
        c = int(to_num(r[1] if len(r) > 1 else 0))
        g = int(to_num(r[2] if len(r) > 2 else 0))
        chromebooks.append({"escola": escola.upper(), "chromebooks": c, "gabinetes": g})
        total_chrome += c
        total_gabinetes += g
    equip_por_gabinete = round(total_chrome / total_gabinetes, 8) if total_gabinetes else 0

    # ---------- SEGURANÇA (Vigia Mais MT) ----------
    vigia = []
    total_cameras = 0
    sem_camera = 0
    danificadas = 0
    for r in vigia_rows:
        escola = clean(r[1] if len(r) > 1 else "")
        if not escola:
            continue
        cams = int(to_num(r[2] if len(r) > 2 else 0))
        status = clean(r[3] if len(r) > 3 else "")
        vigia.append({"municipio": fix_municipio(r[0] if len(r) > 0 else ""), "escola": escola.upper(), "cameras": cams})
        total_cameras += cams
        if cams == 0:
            sem_camera += 1
        if contains(status, "danificadas"):
            danificadas += 1
    unidades_vigia = len(vigia)
    media_cameras = round(total_cameras / unidades_vigia, 8) if unidades_vigia else 0

    # ---------- dim_unidades (Panorama / Cobertura / escolas) ----------
    escolas = []
    municipios_atendidos = set()
    tem_manut_nao = tem_chromes_sim = tem_vigia_nao = 0
    for r in dim_rows:
        cod = clean(r[0] if len(r) > 0 else "")
        nome = clean(r[1] if len(r) > 1 else "")
        if not nome:
            continue
        municipio = fix_municipio(r[2] if len(r) > 2 else "")
        escolas.append({"cod": cod, "escola": nome.upper(), "municipio": municipio})
        if municipio:
            municipios_atendidos.add(municipio)
        tem_manut = clean(r[6] if len(r) > 6 else "")
        tem_chromes = clean(r[7] if len(r) > 7 else "")
        tem_vigia = clean(r[8] if len(r) > 8 else "")
        if tem_manut.upper() == "NAO":
            tem_manut_nao += 1
        if tem_chromes.upper() == "SIM":
            tem_chromes_sim += 1
        if tem_vigia.upper() == "NAO":
            tem_vigia_nao += 1
    unidades_escolares = len(escolas)

    # ---------- Organize / Metadados ----------
    organize = []
    for r in org_rows:
        pasta = clean(r[0] if len(r) > 0 else "")
        processo = fix_processo(clean(r[1] if len(r) > 1 else ""))
        if not processo:
            continue
        organize.append({"pasta": pasta, "processo": processo, "servidor": clean(r[2] if len(r) > 2 else "")})
    servidores = sum(1 for r in meta_rows if clean(r[0] if len(r) > 0 else ""))

    kpis = {
        "Panorama": [
            {"indicador": "Unidades escolares atendidas", "valor": unidades_escolares, "unidade": "un"},
            {"indicador": "Municípios atendidos", "valor": len(municipios_atendidos), "unidade": "un"},
            {"indicador": "Processos/produtos mapeados", "valor": len(organize), "unidade": "un"},
            {"indicador": "Servidores na COIPT", "valor": servidores, "unidade": "un"},
        ],
        "Convênios": [
            {"indicador": "Convênios monitorados", "valor": len(convenios), "unidade": "un"},
            {"indicador": "Convênios vigentes", "valor": sum(1 for v in conv_situacao if v.upper() == "VIGENTE"), "unidade": "un"},
            {"indicador": "Aguardando prestação de contas", "valor": sum(1 for v in conv_situacao if v.upper() == "AGUARDANDO PRESTAÇÃO DE CONTAS"), "unidade": "un"},
            {"indicador": "Convênios encerrados", "valor": sum(1 for v in conv_situacao if v.upper() == "ENCERRADO"), "unidade": "un"},
            {"indicador": "Obras concluídas", "valor": sum(1 for v in conv_obra if v.upper() == "OBRA CONCLUÍDA"), "unidade": "un"},
            {"indicador": "Obras em execução", "valor": sum(1 for v in conv_obra if v.upper() == "OBRA EM EXECUÇÃO"), "unidade": "un"},
            {"indicador": "Convênios em situação crítica", "valor": sum(1 for v in conv_obra if "resci" in v.lower() or v.upper() == "OBRA PARALISADA"), "unidade": "un"},
            {"indicador": "Execução física média", "valor": round(sum(c["execucao"] for c in convenios) / len(convenios) / 100, 4) if convenios else 0, "unidade": "%"},
            {"indicador": "Municípios com convênio", "valor": len(conv_municipios), "unidade": "un"},
        ],
        "Inventário": [
            {"indicador": "Unidades no inventário 2026", "valor": total_inv, "unidade": "un"},
            {"indicador": "NF enviadas ao NPM", "valor": nf_enviadas, "unidade": "un"},
            {"indicador": "NF paradas na escola", "valor": nf_paradas, "unidade": "un"},
            {"indicador": "Mobiliário tramitado ao NPM", "valor": mob_tramitado, "unidade": "un"},
            {"indicador": "Mobiliário devolvido para correção", "valor": mob_devolvido, "unidade": "un"},
            {"indicador": "Inventário imobiliário no Drive", "valor": drive_enviado, "unidade": "un"},
            {"indicador": "Inservíveis com SIGADOC tramitado", "valor": inserv_tramitado, "unidade": "un"},
            {"indicador": "Inservíveis não iniciados", "valor": inserv_nao_iniciado, "unidade": "un"},
            {"indicador": "Processos de inservíveis abertos", "valor": processos_abertos, "unidade": "un"},
            {"indicador": "Conclusão do inventário mobiliário", "valor": conclusao_mobiliario, "unidade": "%"},
        ],
        "Manutenção": [
            {"indicador": "Solicitações recebidas", "valor": total_solic, "unidade": "un"},
            {"indicador": "Solicitações aprovadas", "valor": aprov, "unidade": "un"},
            {"indicador": "Solicitações rejeitadas", "valor": rejeit, "unidade": "un"},
            {"indicador": "Solicitações em análise", "valor": analis, "unidade": "un"},
            {"indicador": "Taxa de aprovação", "valor": taxa_aprovacao, "unidade": "%"},
            {"indicador": "Valor total analisado", "valor": round(valor_total), "unidade": "R$"},
            {"indicador": "Valor aprovado", "valor": round(valor_aprovado), "unidade": "R$"},
            {"indicador": "Valor não autorizado", "valor": round(valor_rejeitado), "unidade": "R$"},
            {"indicador": "Valor em análise", "valor": round(valor_analisado), "unidade": "R$"},
            {"indicador": "Valor médio por solicitação", "valor": valor_medio, "unidade": "R$"},
            {"indicador": "Unidades atendidas", "valor": unidades_atendidas, "unidade": "un"},
            {"indicador": "Média de solicitações por unidade", "valor": media_por_unidade, "unidade": "un"},
        ],
        "Tecnologia": [
            {"indicador": "Chromebooks em operação", "valor": total_chrome, "unidade": "un"},
            {"indicador": "Gabinetes de recarga", "valor": total_gabinetes, "unidade": "un"},
            {"indicador": "Equipamentos por gabinete", "valor": equip_por_gabinete, "unidade": "un"},
        ],
        "Segurança": [
            {"indicador": "Unidades no Vigia Mais MT", "valor": unidades_vigia, "unidade": "un"},
            {"indicador": "Câmeras integradas", "valor": total_cameras, "unidade": "un"},
            {"indicador": "Média de câmeras por unidade", "valor": media_cameras, "unidade": "un"},
            {"indicador": "Unidades sem câmera integrada", "valor": sem_camera, "unidade": "un"},
            {"indicador": "Unidades com câmeras danificadas", "valor": danificadas, "unidade": "un"},
        ],
        "Locação": [
            {"indicador": "Contratos de locação ativos", "valor": contratos_ativos, "unidade": "un"},
            {"indicador": "Vigências a vencer em 90 dias", "valor": vigencias_90, "unidade": "un"},
            {"indicador": "Processos em instrução", "valor": processos_instrucao, "unidade": "un"},
        ],
        "Cobertura": [
            {"indicador": "UEs fora do Vigia Mais MT", "valor": tem_vigia_nao, "unidade": "un"},
            {"indicador": "UEs sem solicitação de manutenção", "valor": tem_manut_nao, "unidade": "un"},
            {"indicador": "UEs com parque de chromebooks", "valor": tem_chromes_sim, "unidade": "un"},
        ],
        "Controle": [
            {"indicador": "Convênios atualizados nos últimos 30 dias", "valor": conv_atualizadas_30d, "unidade": "un"},
        ],
    }

    return {
        "convenios": convenios,
        "inventario": inventario,
        "locacao": locacao,
        "manutencao": manutencao,
        "chromebooks": chromebooks,
        "vigia": vigia,
        "escolas": escolas,
        "organize": organize,
        "kpis": kpis,
        "atualizacao": datetime.utcnow().isoformat(sep=" ", timespec="milliseconds"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-id", required=True, help="ID da planilha Google Sheets (da URL)")
    ap.add_argument("--out", default="data.json", help="Caminho de saída do data.json")
    args = ap.parse_args()

    import json
    data = build(args.sheet_id)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {args.out} gerado com {len(data['inventario'])} unidades no inventário, "
          f"{len(data['manutencao'])} unidades com manutenção, "
          f"{len(data['organize'])} processos/produtos.")


if __name__ == "__main__":
    sys.exit(main())
