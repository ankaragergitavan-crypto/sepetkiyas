"""Sepet PDF çıktısı — telefon/PC indirme."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "fonts"
FONT_REG = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

_SYSTEM_FONTS = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
]


def _resolve_fonts() -> tuple[str, str]:
    if FONT_REG.exists():
        bold = FONT_BOLD if FONT_BOLD.exists() else FONT_REG
        return str(FONT_REG), str(bold)
    regular = next((p for p in _SYSTEM_FONTS if p.exists() and "Bold" not in p.name and "bd" not in p.name.lower()), None)
    bold = next((p for p in _SYSTEM_FONTS if p.exists() and ("Bold" in p.name or "bd" in p.name.lower())), None)
    if regular:
        return str(regular), str(bold or regular)
    raise FileNotFoundError(
        "PDF için Unicode font bulunamadı. backend/fonts/DejaVuSans.ttf ekleyin."
    )


def _money(n: float) -> str:
    return f"{float(n):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")


class CartPDF(FPDF):
    def footer(self) -> None:  # noqa: N802
        self.set_y(-12)
        self.set_font("CartFont", size=8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"AGT MARKET KARŞILAŞTIRMA · sayfa {self.page_no()}/{{nb}}", align="C")


def build_carts_pdf(payload: dict[str, Any]) -> bytes:
    carts = payload.get("carts") or {}
    city = payload.get("cityLabel") or "Ankara"
    note = payload.get("note") or ""
    created = datetime.now().strftime("%d.%m.%Y %H:%M")

    markets: list[dict[str, Any]] = []
    for market_id, items in carts.items():
        if not items:
            continue
        total = sum(float(i.get("price") or 0) * int(i.get("qty") or 0) for i in items)
        qty = sum(int(i.get("qty") or 0) for i in items)
        label = (items[0].get("marketLabel") if items else None) or market_id
        markets.append(
            {
                "marketId": market_id,
                "label": label,
                "items": items,
                "total": total,
                "qty": qty,
            }
        )
    markets.sort(key=lambda m: m["total"])

    if not markets:
        raise ValueError("PDF için sepet boş")

    font_reg, font_bold = _resolve_fonts()
    pdf = CartPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("CartFont", "", font_reg)
    pdf.add_font("CartFont", "B", font_bold)
    pdf.add_page()

    pdf.set_font("CartFont", "B", 18)
    pdf.set_text_color(15, 40, 28)
    pdf.cell(0, 10, "AGT MARKET KARŞILAŞTIRMA — Sepetler", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("CartFont", size=10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Tarih: {created}  ·  Konum: {city}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        "Canlı market fiyatlarından oluşturuldu. Detaylı sepet dökümü.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    if note:
        pdf.multi_cell(0, 5, note)
    pdf.ln(2)

    # Grup özeti
    pdf.set_font("CartFont", "B", 12)
    pdf.set_text_color(15, 40, 28)
    pdf.cell(0, 8, "Market grupları — toplam tutarlar", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    for i, m in enumerate(markets):
        cheapest = i == 0
        pdf.set_font("CartFont", "B" if cheapest else "", 11)
        pdf.set_text_color(20, 110, 60) if cheapest else pdf.set_text_color(30, 30, 30)
        tag = "  [en ucuz]" if cheapest else ""
        pdf.cell(
            0,
            7,
            f"{m['label']}{tag}  ·  {m['qty']} ürün  ·  {_money(m['total'])}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    winner = markets[0]
    pdf.ln(2)
    pdf.set_font("CartFont", "B", 11)
    pdf.set_text_color(20, 110, 60)
    pdf.multi_cell(
        0,
        6,
        f"Öneri: En uygun sepet grubu {winner['label']} — {_money(winner['total'])}",
    )
    pdf.ln(2)

    # Detaylar
    for i, m in enumerate(markets):
        pdf.set_font("CartFont", "B", 12)
        pdf.set_text_color(15, 40, 28)
        title = f"{m['label']} sepeti"
        if i == 0:
            title += " (en ucuz)"
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(1)

        # header
        pdf.set_font("CartFont", "B", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(95, 6, "Ürün", border=0)
        pdf.cell(20, 6, "Adet", border=0, align="R")
        pdf.cell(35, 6, "Birim", border=0, align="R")
        pdf.cell(40, 6, "Satır tutarı", border=0, align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("CartFont", size=9)
        pdf.set_text_color(25, 25, 25)
        for item in m["items"]:
            title_txt = str(item.get("title") or "Ürün")
            qty = int(item.get("qty") or 0)
            price = float(item.get("price") or 0)
            line = price * qty
            # wrap long titles
            x_before = pdf.get_x()
            y_before = pdf.get_y()
            pdf.multi_cell(95, 5, title_txt, border=0)
            y_after = pdf.get_y()
            row_h = max(6, y_after - y_before)
            pdf.set_xy(x_before + 95, y_before)
            pdf.cell(20, row_h, str(qty), align="R")
            pdf.cell(35, row_h, _money(price), align="R")
            pdf.cell(40, row_h, _money(line), align="R", new_x="LMARGIN", new_y="NEXT")
            if pdf.get_y() < y_after:
                pdf.set_y(y_after)

        pdf.set_font("CartFont", "B", 10)
        pdf.set_text_color(15, 40, 28)
        pdf.cell(0, 7, f"{m['label']} sepet toplamı: {_money(m['total'])}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.set_font("CartFont", size=8)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(
        0,
        4,
        "Not: Fiyatlar PDF oluşturulduğu andaki canlı kayıtlara aittir. "
        "Market API’si stok garantisi vermez. AGT MARKET KARŞILAŞTIRMA tıbbi tavsiye sunmaz.",
    )

    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()
