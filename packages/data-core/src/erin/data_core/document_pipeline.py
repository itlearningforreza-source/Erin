"""
ERIN Data Core - Document Intelligence Pipeline
Document type detection, text/table extraction, financial statement parsing, and extraction validation.
"""

import asyncio
import hashlib
import io
import json
import logging
import mimetypes
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Set, Tuple, BinaryIO
from collections import defaultdict

import structlog

logger = structlog.get_logger(__name__)


class DocumentType(str, Enum):
    """Detected document types."""
    PDF = "pdf"
    HTML = "html"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    TXT = "txt"
    UNKNOWN = "unknown"


class FinancialStatementType(str, Enum):
    """Types of financial statements."""
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"
    STATEMENT_OF_CHANGES_EQUITY = "statement_of_changes_equity"
    NOTES = "notes"
    UNKNOWN = "unknown"


@dataclass
class ExtractedTable:
    """A table extracted from a document."""
    table_id: str = field(default_factory=lambda: f"tbl_{uuid.uuid4().hex[:8]}")
    page: int = 0
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedText:
    """Text extracted from a document."""
    text: str
    page: int = 0
    bbox: Optional[Tuple[float, float, float, float]] = None
    font_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentMetadata:
    """Metadata about a processed document."""
    document_id: str = field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    source_id: str = ""
    source_url: str = ""
    filename: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN
    mime_type: str = ""
    file_size: int = 0
    page_count: int = 0
    language: str = "id"
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = ""
    tables_count: int = 0
    text_length: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialFact:
    """A financial fact extracted from a document."""
    concept: str
    value: Any
    fact_id: str = field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    unit: str = "IDR"
    period: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    statement_type: FinancialStatementType = FinancialStatementType.UNKNOWN
    page_reference: int = 0
    table_reference: Optional[str] = None
    row_reference: Optional[int] = None
    column_reference: Optional[str] = None
    confidence: float = 1.0
    source_document_id: str = ""
    extraction_method: str = ""
    raw_context: str = ""
    validated: bool = False
    validation_notes: str = ""


@dataclass
class EntityExtraction:
    """Named entity extracted from document."""
    text: str
    label: str
    start_char: int
    end_char: int
    page: int
    entity_id: str = field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:8]}")
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of document processing."""
    success: bool
    document_metadata: Optional[DocumentMetadata] = None
    tables: List[ExtractedTable] = field(default_factory=list)
    texts: List[ExtractedText] = field(default_factory=list)
    financial_facts: List[FinancialFact] = field(default_factory=list)
    entities: List[EntityExtraction] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class DocumentDetector:
    """Detects document type from content."""

    MAGIC_BYTES = {
        b'%PDF': DocumentType.PDF,
        b'PK\x03\x04': DocumentType.XLSX,
        b'\xd0\xcf\x11\xe0': DocumentType.XLS,
        b'<?xml': DocumentType.XML,
        b'{': DocumentType.JSON,
    }

    @classmethod
    def detect(cls, content: bytes, filename: str = "", mime_type: str = "") -> DocumentType:
        """Detect document type from content, filename, and mime type."""
        for magic, doc_type in cls.MAGIC_BYTES.items():
            if content.startswith(magic):
                if doc_type == DocumentType.XLSX:
                    if filename.lower().endswith(('.xlsx', '.xlsm')):
                        return DocumentType.XLSX
                return doc_type

        if filename:
            ext = Path(filename).suffix.lower()
            ext_map = {
                '.pdf': DocumentType.PDF,
                '.xlsx': DocumentType.XLSX,
                '.xlsm': DocumentType.XLSX,
                '.xls': DocumentType.XLS,
                '.csv': DocumentType.CSV,
                '.json': DocumentType.JSON,
                '.xml': DocumentType.XML,
                '.html': DocumentType.HTML,
                '.htm': DocumentType.HTML,
                '.txt': DocumentType.TXT,
            }
            if ext in ext_map:
                return ext_map[ext]

        if mime_type:
            mime_map = {
                'application/pdf': DocumentType.PDF,
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': DocumentType.XLSX,
                'application/vnd.ms-excel': DocumentType.XLS,
                'text/csv': DocumentType.CSV,
                'application/json': DocumentType.JSON,
                'application/xml': DocumentType.XML,
                'text/xml': DocumentType.XML,
                'text/html': DocumentType.HTML,
                'text/plain': DocumentType.TXT,
            }
            if mime_type in mime_map:
                return mime_map[mime_type]

        try:
            text = content.decode('utf-8')
            if text.strip().startswith('{'):
                return DocumentType.JSON
            elif text.strip().startswith('<'):
                return DocumentType.HTML if '<html' in text.lower() else DocumentType.XML
            elif ',' in text and '\n' in text:
                return DocumentType.CSV
        except UnicodeDecodeError:
            pass

        return DocumentType.UNKNOWN


class PDFExtractor:
    """Extracts text and tables from PDF documents."""

    def __init__(self):
        self._pdfplumber_available = self._check_pdfplumber()
        self._camelot_available = self._check_camelot()
        self._tabula_available = self._check_tabula()

    def _check_pdfplumber(self) -> bool:
        try:
            import pdfplumber
            return True
        except ImportError:
            return False

    def _check_camelot(self) -> bool:
        try:
            import camelot
            return True
        except ImportError:
            return False

    def _check_tabula(self) -> bool:
        try:
            import tabula
            return True
        except ImportError:
            return False

    async def extract(self, content: bytes, filename: str = "") -> ProcessingResult:
        """Extract text and tables from PDF."""
        start_time = datetime.now(timezone.utc)
        result = ProcessingResult(success=False)

        if not self._pdfplumber_available:
            result.errors.append("pdfplumber not available")
            return result

        try:
            import pdfplumber

            tables = []
            texts = []

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        texts.append(ExtractedText(
                            text=text,
                            page=page_num + 1,
                            bbox=page.bbox
                        ))

                    page_tables = page.extract_tables()
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 1:
                            headers = [str(h) if h else f"col_{i}" for i, h in enumerate(table[0])]
                            rows = [[str(c) if c else "" for c in row] for row in table[1:]]

                            tables.append(ExtractedTable(
                                page=page_num + 1,
                                headers=headers,
                                rows=rows,
                                bbox=page.bbox,
                                metadata={"table_index": table_idx}
                            ))

            content_hash = hashlib.sha256(content).hexdigest()[:16]

            metadata = DocumentMetadata(
                filename=filename,
                document_type=DocumentType.PDF,
                mime_type="application/pdf",
                file_size=len(content),
                page_count=page_count,
                content_hash=content_hash,
                tables_count=len(tables),
                text_length=sum(len(t.text) for t in texts)
            )

            result.success = True
            result.document_metadata = metadata
            result.tables = tables
            result.texts = texts

        except Exception as e:
            result.errors.append(f"PDF extraction failed: {str(e)}")
            logger.error("PDF extraction error", error=str(e))

        result.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return result


class HTMLExtractor:
    """Extracts structured data from HTML documents."""

    async def extract(self, content: bytes, filename: str = "") -> ProcessingResult:
        """Extract text and tables from HTML."""
        start_time = datetime.now(timezone.utc)
        result = ProcessingResult(success=False)

        try:
            from bs4 import BeautifulSoup

            text = content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(text, 'html.parser')

            tables = []
            texts = []

            for script in soup(["script", "style"]):
                script.decompose()

            body_text = soup.get_text(separator='\n', strip=True)
            if body_text:
                texts.append(ExtractedText(text=body_text, page=0))

            for table_idx, table in enumerate(soup.find_all('table')):
                table_data = self._parse_html_table(table)
                if table_data and len(table_data) > 1:
                    headers = table_data[0]
                    rows = table_data[1:]

                    tables.append(ExtractedTable(
                        page=0,
                        headers=[str(h) for h in headers],
                        rows=[[str(c) for c in r] for r in rows],
                        metadata={"table_index": table_idx}
                    ))

            financial_facts = []
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    ld_data = json.loads(script.string)
                    if isinstance(ld_data, list):
                        for item in ld_data:
                            facts = self._extract_facts_from_json_ld(item)
                            financial_facts.extend(facts)
                    else:
                        facts = self._extract_facts_from_json_ld(ld_data)
                        financial_facts.extend(facts)
                except:
                    pass

            content_hash = hashlib.sha256(content).hexdigest()[:16]

            metadata = DocumentMetadata(
                filename=filename,
                document_type=DocumentType.HTML,
                mime_type="text/html",
                file_size=len(content),
                page_count=1,
                content_hash=content_hash,
                tables_count=len(tables),
                text_length=len(body_text)
            )

            result.success = True
            result.document_metadata = metadata
            result.tables = tables
            result.texts = texts
            result.financial_facts = financial_facts

        except Exception as e:
            result.errors.append(f"HTML extraction failed: {str(e)}")
            logger.error("HTML extraction error", error=str(e))

        result.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return result

    def _parse_html_table(self, table) -> List[List[str]]:
        """Parse HTML table to list of rows."""
        rows = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            row = [cell.get_text(strip=True) for cell in cells]
            if row:
                rows.append(row)
        return rows

    def _extract_facts_from_json_ld(self, data: Dict[str, Any]) -> List[FinancialFact]:
        """Extract financial facts from JSON-LD structured data."""
        facts = []

        financial_concepts = {
            'revenue': 'Revenue',
            'netIncome': 'Net Income',
            'totalAssets': 'Total Assets',
            'totalLiabilities': 'Total Liabilities',
            'totalEquity': 'Total Equity',
            'operatingIncome': 'Operating Income',
            'cashAndCashEquivalents': 'Cash and Cash Equivalents',
        }

        for key, concept in financial_concepts.items():
            if key in data:
                value = data[key]
                if isinstance(value, dict) and 'value' in value:
                    facts.append(FinancialFact(
                        concept=concept,
                        value=value['value'],
                        unit=value.get('unitText', 'IDR'),
                        extraction_method="json_ld",
                        raw_context=json.dumps(value)
                    ))
                elif isinstance(value, (int, float, str)):
                    facts.append(FinancialFact(
                        concept=concept,
                        value=value,
                        extraction_method="json_ld",
                        raw_context=str(value)
                    ))

        return facts


class SpreadsheetExtractor:
    """Extracts data from spreadsheet files (XLSX, XLS, CSV)."""

    async def extract(self, content: bytes, filename: str = "", doc_type: DocumentType = DocumentType.UNKNOWN) -> ProcessingResult:
        """Extract data from spreadsheet."""
        start_time = datetime.now(timezone.utc)
        result = ProcessingResult(success=False)

        try:
            tables = []

            if doc_type in [DocumentType.XLSX, DocumentType.XLS]:
                tables = await self._extract_excel(content)
            elif doc_type == DocumentType.CSV:
                tables = await self._extract_csv(content)

            content_hash = hashlib.sha256(content).hexdigest()[:16]

            metadata = DocumentMetadata(
                filename=filename,
                document_type=doc_type,
                mime_type=self._get_mime_type(doc_type),
                file_size=len(content),
                page_count=len(tables),
                content_hash=content_hash,
                tables_count=len(tables),
                text_length=sum(len(str(r)) for t in tables for r in t.rows)
            )

            result.success = True
            result.document_metadata = metadata
            result.tables = tables

        except Exception as e:
            result.errors.append(f"Spreadsheet extraction failed: {str(e)}")
            logger.error("Spreadsheet extraction error", error=str(e))

        result.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return result

    def _get_mime_type(self, doc_type: DocumentType) -> str:
        mime_map = {
            DocumentType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            DocumentType.XLS: "application/vnd.ms-excel",
            DocumentType.CSV: "text/csv",
        }
        return mime_map.get(doc_type, "application/octet-stream")

    async def _extract_excel(self, content: bytes) -> List[ExtractedTable]:
        """Extract tables from Excel file."""
        try:
            import openpyxl
        except ImportError:
            raise Exception("openpyxl not available")

        tables = []
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)

        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            ws = wb[sheet_name]
            headers = None
            rows = []

            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx == 0:
                    headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(row)]
                else:
                    if any(c is not None for c in row):
                        rows.append([str(c) if c is not None else "" for c in row])

            if headers and rows:
                tables.append(ExtractedTable(
                    page=sheet_idx,
                    headers=headers,
                    rows=rows,
                    metadata={"sheet_name": sheet_name}
                ))

        return tables

    async def _extract_csv(self, content: bytes) -> List[ExtractedTable]:
        """Extract table from CSV."""
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1')

        import csv
        reader = csv.reader(io.StringIO(text))
        all_rows = list(reader)

        if not all_rows:
            return []

        headers = [str(h) if h else f"col_{i}" for i, h in enumerate(all_rows[0])]
        rows = [[str(c) for c in row] for row in all_rows[1:]]

        return [ExtractedTable(
            page=0,
            headers=headers,
            rows=rows
        )]


class JSONExtractor:
    """Extracts structured data from JSON documents."""

    async def extract(self, content: bytes, filename: str = "") -> ProcessingResult:
        """Extract data from JSON."""
        start_time = datetime.now(timezone.utc)
        result = ProcessingResult(success=False)

        try:
            text = content.decode('utf-8')
            data = json.loads(text)

            tables = []
            financial_facts = []

            if isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[str(item.get(h, "")) for h in headers] for item in data]
                tables.append(ExtractedTable(page=0, headers=headers, rows=rows))
            elif isinstance(data, dict):
                headers = list(data.keys())
                rows = [[str(data.get(h, "")) for h in headers]]
                tables.append(ExtractedTable(page=0, headers=headers, rows=rows))

                financial_facts = self._extract_financial_facts(data)

            content_hash = hashlib.sha256(content).hexdigest()[:16]

            metadata = DocumentMetadata(
                filename=filename,
                document_type=DocumentType.JSON,
                mime_type="application/json",
                file_size=len(content),
                page_count=1,
                content_hash=content_hash,
                tables_count=len(tables),
                text_length=len(text)
            )

            result.success = True
            result.document_metadata = metadata
            result.tables = tables
            result.financial_facts = financial_facts

        except Exception as e:
            result.errors.append(f"JSON extraction failed: {str(e)}")
            logger.error("JSON extraction error", error=str(e))

        result.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return result

    def _extract_financial_facts(self, data: Dict[str, Any]) -> List[FinancialFact]:
        """Extract financial facts from JSON object."""
        facts = []

        financial_concepts = {
            'revenue': 'Revenue',
            'net_income': 'Net Income',
            'netIncome': 'Net Income',
            'total_assets': 'Total Assets',
            'totalAssets': 'Total Assets',
            'total_liabilities': 'Total Liabilities',
            'totalLiabilities': 'Total Liabilities',
            'total_equity': 'Total Equity',
            'totalEquity': 'Total Equity',
            'operating_income': 'Operating Income',
            'operatingIncome': 'Operating Income',
            'cash_and_cash_equivalents': 'Cash and Cash Equivalents',
            'cashAndCashEquivalents': 'Cash and Cash Equivalents',
            'eps': 'Earnings Per Share',
            'earningsPerShare': 'Earnings Per Share',
        }

        for key, concept in financial_concepts.items():
            if key in data:
                value = data[key]
                if isinstance(value, dict) and 'value' in value:
                    facts.append(FinancialFact(
                        concept=concept,
                        value=value['value'],
                        unit=value.get('unit', 'IDR'),
                        extraction_method="json",
                        raw_context=json.dumps(value)
                    ))
                elif isinstance(value, (int, float, str)):
                    facts.append(FinancialFact(
                        concept=concept,
                        value=value,
                        extraction_method="json",
                        raw_context=str(value)
                    ))

        return facts


class FinancialStatementParser:
    """Parses financial statements from extracted tables."""

    def __init__(self):
        self.statement_keywords = {
            FinancialStatementType.BALANCE_SHEET: [
                'balance sheet', 'statement of financial position',
                'neraca', 'posisi keuangan'
            ],
            FinancialStatementType.INCOME_STATEMENT: [
                'income statement', 'statement of comprehensive income',
                'profit and loss', 'laba rugi', 'penghasilan komprehensif'
            ],
            FinancialStatementType.CASH_FLOW: [
                'cash flow', 'statement of cash flows',
                'arus kas', 'laporan arus kas'
            ],
            FinancialStatementType.STATEMENT_OF_CHANGES_EQUITY: [
                'changes in equity', 'statement of changes in equity',
                'perubahan ekuitas', 'laporan perubahan ekuitas'
            ],
        }

        self.line_item_patterns = {
            'revenue': [r'revenue', r'pendapatan', r'penjualan', r'sales', r'net sales'],
            'cost_of_goods_sold': [r'cost of goods sold', r'harga pokok', r'cogs', r'cost of sales'],
            'gross_profit': [r'gross profit', r'laba kotor', r'gross margin'],
            'operating_expenses': [r'operating expense', r'beban operasi', r'opex'],
            'operating_income': [r'operating income', r'laba operasi', r'operating profit'],
            'net_income': [r'net income', r'laba bersih', r'profit after tax', r'net profit'],
            'total_assets': [r'total assets', r'total aset', r'jumlah aset'],
            'total_liabilities': [r'total liabilities', r'total liabilitas', r'jumlah kewajiban'],
            'total_equity': [r'total equity', r'total ekuitas', r'jumlah ekuitas', r'shareholders equity'],
            'cash': [r'cash and cash equivalent', r'kas dan setara kas', r'cash and bank'],
            'accounts_receivable': [r'accounts receivable', r'piutang usaha', r'trade receivables'],
            'inventory': [r'inventory', r'persediaan', r'stock'],
            'property_plant_equipment': [r'property, plant and equipment', r'aset tetap', r'ppe'],
            'accounts_payable': [r'accounts payable', r'hutang usaha', r'trade payables'],
            'short_term_debt': [r'short.?term debt', r'hutang jangka pendek', r'current portion'],
            'long_term_debt': [r'long.?term debt', r'hutang jangka panjang', r'non.?current'],
        }

    def identify_statement_type(self, table: ExtractedTable) -> FinancialStatementType:
        """Identify the type of financial statement from table headers/content."""
        search_text = ' '.join(table.headers + [str(r) for row in table.rows[:5] for r in row]).lower()

        scores = {}
        for stmt_type, keywords in self.statement_keywords.items():
            score = sum(1 for kw in keywords if kw in search_text)
            if score > 0:
                scores[stmt_type] = score

        if scores:
            return max(scores, key=scores.get)
        return FinancialStatementType.UNKNOWN

    def parse_statement(self, table: ExtractedTable, statement_type: FinancialStatementType, period: str = "", document_id: str = "") -> List[FinancialFact]:
        """Parse a financial statement table into structured facts."""
        facts = []

        if not table.headers or not table.rows:
            return facts

        value_col_idx = self._find_value_column(table)
        if value_col_idx is None:
            value_col_idx = len(table.headers) - 1

        label_col_idx = 0

        for row_idx, row in enumerate(table.rows):
            if len(row) <= max(label_col_idx, value_col_idx):
                continue

            label = str(row[label_col_idx]).strip()
            value_str = str(row[value_col_idx]).strip()

            if not label or not value_str:
                continue

            value = self._parse_numeric_value(value_str)
            if value is None:
                continue

            concept = self._identify_concept(label)
            if not concept:
                concept = label

            unit = self._detect_unit(label, table.headers[value_col_idx] if value_col_idx < len(table.headers) else "")

            facts.append(FinancialFact(
                concept=concept,
                value=value,
                unit=unit,
                period=period,
                statement_type=statement_type,
                page_reference=table.page,
                table_reference=table.table_id,
                row_reference=row_idx,
                column_reference=table.headers[value_col_idx] if value_col_idx < len(table.headers) else "",
                extraction_method="table_parsing",
                raw_context=f"Label: {label}, Value: {value_str}, Header: {table.headers[value_col_idx] if value_col_idx < len(table.headers) else ''}"
            ))

        return facts

    def _find_value_column(self, table: ExtractedTable) -> Optional[int]:
        """Find the column containing numeric values."""
        if not table.rows:
            return None

        col_scores = defaultdict(int)
        for row in table.rows[:20]:
            for i, cell in enumerate(row):
                if self._parse_numeric_value(str(cell)) is not None:
                    col_scores[i] += 1

        if col_scores:
            return max(col_scores, key=col_scores.get)
        return None

    def _parse_numeric_value(self, value_str: str) -> Optional[float]:
        """Parse numeric value from string, handling various formats."""
        if not value_str:
            return None

        cleaned = value_str.strip()

        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]

        cleaned = re.sub(r'[Rp$\u20ac\u00a3\u00a5\s,]', '', cleaned)

        if ',' in cleaned and '.' in cleaned:
            last_comma = cleaned.rfind(',')
            last_dot = cleaned.rfind('.')
            if last_comma > last_dot:
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts[-1]) <= 2 and len(parts) > 1:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _identify_concept(self, label: str) -> Optional[str]:
        """Identify financial concept from label."""
        label_lower = label.lower()

        for concept, patterns in self.line_item_patterns.items():
            for pattern in patterns:
                if re.search(pattern, label_lower):
                    return concept.replace('_', ' ').title()

        return None

    def _detect_unit(self, label: str, header: str) -> str:
        """Detect unit from label or header."""
        text = (label + ' ' + header).lower()

        if any(kw in text for kw in ['million', 'juta', 'jt']):
            return 'IDR Million'
        elif any(kw in text for kw in ['billion', 'miliar', 'm']):
            return 'IDR Billion'
        elif any(kw in text for kw in ['trillion', 'triliun', 't']):
            return 'IDR Trillion'
        elif any(kw in text for kw in ['percent', '%', 'persen']):
            return 'Percentage'
        elif any(kw in text for kw in ['ratio', 'rasio']):
            return 'Ratio'
        elif any(kw in text for kw in ['usd', 'dollar']):
            return 'USD'
        elif any(kw in text for kw in ['idr', 'rupiah', 'rp']):
            return 'IDR'

        return 'IDR'


class DocumentPipeline:
    """Main document processing pipeline."""

    def __init__(self):
        self.detector = DocumentDetector()
        self.pdf_extractor = PDFExtractor()
        self.html_extractor = HTMLExtractor()
        self.spreadsheet_extractor = SpreadsheetExtractor()
        self.json_extractor = JSONExtractor()
        self.statement_parser = FinancialStatementParser()
        self._entity_extractor = None

    async def process(self, content: bytes, filename: str = "", source_id: str = "", source_url: str = "", mime_type: str = "") -> ProcessingResult:
        """Process a document through the full pipeline."""
        start_time = datetime.now(timezone.utc)

        doc_type = self.detector.detect(content, filename, mime_type)

        if doc_type == DocumentType.PDF:
            result = await self.pdf_extractor.extract(content, filename)
        elif doc_type == DocumentType.HTML:
            result = await self.html_extractor.extract(content, filename)
        elif doc_type in [DocumentType.XLSX, DocumentType.XLS, DocumentType.CSV]:
            result = await self.spreadsheet_extractor.extract(content, filename, doc_type)
        elif doc_type == DocumentType.JSON:
            result = await self.json_extractor.extract(content, filename)
        else:
            result = ProcessingResult(success=False, errors=[f"Unsupported document type: {doc_type}"])

        if not result.success:
            return result

        if result.document_metadata:
            result.document_metadata.source_id = source_id
            result.document_metadata.source_url = source_url

        all_facts = list(result.financial_facts)
        for table in result.tables:
            stmt_type = self.statement_parser.identify_statement_type(table)
            if stmt_type != FinancialStatementType.UNKNOWN:
                facts = self.statement_parser.parse_statement(table, stmt_type, document_id=result.document_metadata.document_id)
                all_facts.extend(facts)

        result.financial_facts = all_facts

        result.entities = await self._extract_entities(result.texts)

        result.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return result

    async def _extract_entities(self, texts: List[ExtractedText]) -> List[EntityExtraction]:
        """Extract named entities using spaCy."""
        entities = []

        if self._entity_extractor is None:
            try:
                import spacy
                self._entity_extractor = spacy.load("en_core_web_sm")
            except Exception:
                logger.warning("spaCy not available for entity extraction")
                return entities

        for text_obj in texts:
            doc = self._entity_extractor(text_obj.text[:50000])
            for ent in doc.ents:
                entities.append(EntityExtraction(
                    text=ent.text,
                    label=ent.label_,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    page=text_obj.page,
                    confidence=0.8
                ))

        return entities

    async def process_from_source(self, source, content: bytes, filename: str = "") -> ProcessingResult:
        """Process document from a registered source."""
        return await self.process(content, filename, source.source_id, source.config.base_url)


async def process_document(content: bytes, filename: str = "", source_id: str = "", source_url: str = "", mime_type: str = "") -> ProcessingResult:
    """Process a document through the pipeline."""
    pipeline = DocumentPipeline()
    return await pipeline.process(content, filename, source_id, source_url, mime_type)


if __name__ == "__main__":
    async def test():
        pipeline = DocumentPipeline()

        print("Testing document detector...")
        assert pipeline.detector.detect(b"%PDF-1.4 test", "test.pdf") == DocumentType.PDF
        assert pipeline.detector.detect(b"PK\x03\x04", "test.xlsx") == DocumentType.XLSX
        assert pipeline.detector.detect(b"col1,col2\n1,2", "test.csv") == DocumentType.CSV
        assert pipeline.detector.detect(b'{"key": "value"}', "test.json") == DocumentType.JSON
        assert pipeline.detector.detect(b"<html><body>test</body></html>", "test.html") == DocumentType.HTML
        print("Document detector tests passed!")

        parser = FinancialStatementParser()
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Revenue", "1,000,000", "900,000"],
                ["Net Income", "100,000", "80,000"],
                ["Total Assets", "5,000,000", "4,500,000"]
            ]
        )
        stmt_type = parser.identify_statement_type(table)
        print(f"Statement type: {stmt_type}")

        facts = parser.parse_statement(table, stmt_type, "2023-FY")
        print(f"Extracted {len(facts)} facts:")
        for f in facts:
            print(f"  {f.concept}: {f.value} {f.unit} ({f.period})")

        print("\nAll document pipeline tests passed!")

    asyncio.run(test())
