from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class NormalizedBlock(BaseModel):
    block_id: str
    source_type: str # pdf, docx, md, xlsx, csv
    block_type: str  # heading, paragraph, list, code, table, table_group
    content: str
    heading_path: List[str] = []
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    table_id: Optional[str] = None
    source_order: int = 0

    model_config = ConfigDict(from_attributes=True)
