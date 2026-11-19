from .config import list_brands, load_profile


def convert(md_text, brand_id, model_id, fmt):
    """Ritorna (bytes, nome_file, mimetype)."""
    prof = load_profile(brand_id, model_id)
    if fmt == "pdf":
        from .pdf import build_pdf
        data, slug = build_pdf(md_text, prof)
        return data, f"{slug}.pdf", "application/pdf"
    if fmt == "docx":
        from .docx_ import build_docx
        data, slug = build_docx(md_text, prof)
        return data, f"{slug}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == "pptx":
        from .pptx_ import build_pptx
        data, slug = build_pptx(md_text, prof)
        return data, f"{slug}.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    raise ValueError(f"Formato non supportato: {fmt}")
