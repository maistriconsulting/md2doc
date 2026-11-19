from .config import list_brands, load_profile
from .nomi import nome_file
from .parser import split_front_matter


def convert(md_text, brand_id, model_id, fmt, nome_base=None):
    """Ritorna (bytes, nome_file, mimetype). Il nome e' <nome del markdown>_<data di release>."""
    prof = load_profile(brand_id, model_id)
    meta = split_front_matter(md_text)[0]
    if fmt == "pdf":
        from .pdf import build_pdf
        data, slug = build_pdf(md_text, prof)
        return data, nome_file(meta, nome_base, slug, "pdf"), "application/pdf"
    if fmt == "docx":
        from .docx_ import build_docx
        data, slug = build_docx(md_text, prof)
        return data, nome_file(meta, nome_base, slug, "docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == "pptx":
        from .pptx_ import build_pptx
        data, slug = build_pptx(md_text, prof)
        return data, nome_file(meta, nome_base, slug, "pptx"), "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    raise ValueError(f"Formato non supportato: {fmt}")
