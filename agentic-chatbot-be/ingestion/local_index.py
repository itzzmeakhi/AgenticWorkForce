import re
from typing import List

from config import KNOWLEDGE_BASE_DIR

DOMAIN_BY_FILE = {
    "ecommerce_refund_policy.md": "ecommerce",
    "ecommerce_shipping_policy.md": "ecommerce",
    "insurance_claims_process.md": "insurance",
    "insurance_premiums_and_renewals.md": "insurance",
    "insurance_coverage_and_exclusions.md": "insurance",
    "general_contact_center_faq.md": "general",
}


def _chunk_markdown(text: str) -> List[str]:
    parts = re.split(r"\n(?=## )", text.strip())
    return [p.strip() for p in parts if p.strip()]


def build_local_index(force: bool = False) -> int:
    from agent.knowledge_search import get_backend

    backend = get_backend()

    ids, docs, metadatas = [], [], []
    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        domain = DOMAIN_BY_FILE.get(md_file.name, "general")
        text = md_file.read_text()
        for i, chunk in enumerate(_chunk_markdown(text)):
            ids.append(f"{md_file.stem}-{i}")
            docs.append(chunk)
            metadatas.append({"source": md_file.name, "domain": domain})

    return backend.index_chunks(ids, docs, metadatas, force=force)


if __name__ == "__main__":
    n = build_local_index(force=True)
    print(f"Indexed {n} chunks into the offline Chroma knowledge base.")
