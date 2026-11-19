"""PDF de receita e atestado (G29).

Usa as fontes padrão do PDF (Helvetica), que cobrem o português em Latin-1; caracteres fora dele
(travessão, aspas curvas, emoji) são trocados por equivalentes simples para não quebrar a geração.
O documento não leva assinatura digital: vale impresso e assinado pelo profissional.
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_TROCAS = str.maketrans({
    "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "×": "x", "•": "-", " ": " ",
})

_UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
             "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]

TITULOS = {"RECEITA": "Receita", "ATESTADO": "Atestado"}


def _latin1(texto: object) -> str:
    return str(texto or "").translate(_TROCAS).encode("latin-1", "ignore").decode("latin-1").strip()


def por_extenso(numero: int) -> str:
    """Número de 1 a 99 por extenso."""
    if numero < 20:
        return _UNIDADES[numero]
    dezena, unidade = divmod(numero, 10)
    return _DEZENAS[dezena] + (f" e {_UNIDADES[unidade]}" if unidade else "")


def texto_do_atestado(paciente: str, conteudo: dict, emitido_em: str) -> str:
    dias = int(conteudo["dias"])
    periodo = f"{dias} ({por_extenso(dias)}) {'dia' if dias == 1 else 'dias'}"
    inicio = conteudo.get("a_partir_de") or emitido_em
    texto = (
        f"Atesto, para os devidos fins, que {paciente} foi atendido(a) nesta data e necessita de "
        f"afastamento de suas atividades por {periodo}, a partir de {inicio}."
    )
    if conteudo.get("motivo"):
        texto += f" {conteudo['motivo']}"
    return texto


def gerar_pdf(dados: dict) -> bytes:
    """Monta o PDF. `dados`: tipo, codigo, emitido_em, unidade, profissional, paciente e conteudo."""
    unidade, profissional = dados["unidade"], dados["profissional"]
    paciente = _latin1(dados["paciente"]["nome"])
    conteudo = dados["conteudo"]

    pdf = FPDF(format="A4")
    pdf.set_compression(True)
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(True, margin=42)
    pdf.set_title(f"{TITULOS[dados['tipo']]} - {paciente}")
    pdf.add_page()
    largura = pdf.epw

    def linha(texto: str, tamanho: float = 11, estilo: str = "", altura: float = 6, cor: int = 20) -> None:
        pdf.set_font("Helvetica", estilo, tamanho)
        pdf.set_text_color(cor)
        pdf.multi_cell(largura, altura, _latin1(texto), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Cabeçalho da unidade
    linha(unidade["nome"], 15, "B", 8)
    for extra in (unidade.get("endereco"), unidade.get("telefone")):
        if extra:
            linha(extra, 9.5, altura=5, cor=90)
    pdf.ln(3)
    pdf.set_draw_color(180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + largura, pdf.get_y())
    pdf.ln(8)

    linha(TITULOS[dados["tipo"]].upper(), 14, "B", 8)
    pdf.ln(2)
    linha(f"Paciente: {paciente}", 11.5)
    linha(f"Data: {dados['emitido_em']}", 11.5)
    pdf.ln(6)

    if dados["tipo"] == "RECEITA":
        for numero, item in enumerate(conteudo["itens"], start=1):
            linha(f"{numero}. {item['medicamento']}", 12, "B", 7)
            linha(item["posologia"], 11.5, altura=6.5)
            pdf.ln(3)
        if conteudo.get("observacoes"):
            pdf.ln(2)
            linha(f"Observações: {conteudo['observacoes']}", 11)
    else:
        linha(texto_do_atestado(paciente, conteudo, dados["emitido_em"]), 12, altura=7.5)
        if conteudo.get("cid"):
            pdf.ln(4)
            linha(f"CID: {conteudo['cid']} (informado a pedido do paciente)", 11)

    # Assinatura e rodapé
    pdf.set_y(-78)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(20)
    for texto, estilo in (("_" * 44, ""), (profissional["nome"], "B"), (profissional.get("registro") or "", "")):
        if texto:
            pdf.set_font("Helvetica", estilo, 11)
            pdf.cell(largura, 6, _latin1(texto), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(110)
    pdf.multi_cell(
        largura, 4.5,
        _latin1(
            f"Documento emitido eletronicamente em {dados['emitido_em']}. Código de verificação: {dados['codigo']}. "
            "Válido somente com a assinatura do profissional."
        ),
        align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    return bytes(pdf.output())
