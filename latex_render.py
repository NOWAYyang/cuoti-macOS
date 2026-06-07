"""LaTeX math rendering for PDF generation."""
import re
import io
import base64

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["axes.unicode_minus"] = False


def _render_latex(expr: str) -> bytes | None:
    """Render a LaTeX math expression to PNG bytes."""
    expr = expr.strip()
    expr = re.sub(r"\\boxed\{(.*?)\}", r"\1", expr)
    # Strip math-mode style/display commands that matplotlib mathtext doesn't support
    expr = re.sub(r"\\(displaystyle|textstyle|scriptstyle|limits)\s*", "", expr)
    # Strip \begin{cases} / \end{cases} (matplotlib doesn't support it)
    expr = re.sub(r"\\begin\{cases\}", r"", expr)
    expr = re.sub(r"\\end\{cases\}", r"", expr)
    # Replace \\ line separator in cases/environments with spacing
    expr = re.sub(r"\\\\", r"  ", expr)

    fig, ax = plt.subplots(figsize=(0.01, 0.01))
    ax.axis("off")

    try:
        text = ax.text(0, 0, f"${expr}$", fontsize=13, ha="left", va="bottom")
        fig.canvas.draw()
        bbox = text.get_window_extent(fig.canvas.get_renderer())
        fig.set_size_inches(bbox.width / 80 + 0.3, bbox.height / 80 + 0.2)
        fig.canvas.draw()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05, dpi=150)
        png = buf.getvalue()
        plt.close(fig)
        return png
    except Exception:
        plt.close(fig)
        return None


def _latex_block_to_img_tag(expr: str) -> str:
    """Convert a LaTeX expression to an HTML img tag with base64 PNG."""
    # Extract CJK text from \text{} since matplotlib mathtext doesn't support CJK glyphs
    cjk_parts = []

    def _strip_cjk_text(m):
        inner = m.group(1)
        if re.search(r"[一-鿿　-〿＀-￯]", inner):
            cjk_parts.append(inner)
            return "{}"
        return m.group(0)

    cleaned = re.sub(r"\\text\{([^}]*)\}", _strip_cjk_text, expr)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[\s,;:，；：、+\-=*/]+", "", cleaned)
    cleaned = re.sub(r"[\s,;:，；：、+\-=*/]+$", "", cleaned)

    render_target = expr
    if cjk_parts:
        if cleaned and cleaned != expr:
            render_target = cleaned
        else:
            # Expression is purely CJK text or empty after cleaning - just show the text
            return "".join(cjk_parts)

    png = _render_latex(render_target)
    if png is None:
        return f'<span class="latex-fallback">${expr}$</span>'

    b64 = base64.b64encode(png).decode()
    result = f'<img src="data:image/png;base64,{b64}" class="latex-rendered" alt="{expr}" />'
    for part in cjk_parts:
        result += f'<span class="latex-cjk-text">{part}</span>'
    return result


def render_answer_markdown(text: str) -> str:
    """Convert DeepSeek answer to HTML with LaTeX rendered as images."""
    blocks = []

    def _save_display(m):
        blocks.append(m.group(1))
        return f"%%LATEX_DISPLAY_{len(blocks)-1}%%"

    text = re.sub(r"\$\$(.*?)\$\$", _save_display, text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.*?)\\\]", _save_display, text, flags=re.DOTALL)

    def _save_inline(m):
        blocks.append(m.group(1))
        return f"%%LATEX_INLINE_{len(blocks)-1}%%"

    text = re.sub(r"\\\((.*?)\\\)", _save_inline, text, flags=re.DOTALL)

    # Handle $...$ inline math (single dollar signs)
    # Must be done after $$ and \( are already protected
    def _save_dollar_inline(m):
        # Skip if it looks like currency (e.g., $100, $50.50)
        inner = m.group(1)
        if inner.strip() and not re.match(r'^\d+(\.\d+)?$', inner.strip()):
            blocks.append(inner)
            return f"%%LATEX_INLINE_{len(blocks)-1}%%"
        return m.group(0)

    text = re.sub(r"\$(.+?)\$", _save_dollar_inline, text)

    import markdown as md_lib
    html = md_lib.markdown(text, extensions=["extra"])

    for i, expr in enumerate(blocks):
        placeholder = f"%%LATEX_DISPLAY_{i}%%"
        if placeholder in html:
            html = html.replace(
                placeholder,
                f'<div class="math-block">{_latex_block_to_img_tag(expr)}</div>',
            )
            continue
        placeholder = f"%%LATEX_INLINE_{i}%%"
        if placeholder in html:
            html = html.replace(
                placeholder,
                _latex_block_to_img_tag(expr),
            )

    return html
