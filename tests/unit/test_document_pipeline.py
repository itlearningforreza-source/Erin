"""Unit tests for Document Pipeline."""

import pytest
import sys
sys.path.insert(0, '/home/rezaahmadkhairuddin/ERIN/packages/data-core/src')

from erin.data_core import (
    DocumentPipeline,
    DocumentDetector,
    DocumentType,
    FinancialStatementParser,
    ExtractedTable,
    FinancialStatementType
)


class TestDocumentDetector:
    """Tests for DocumentDetector."""
    
    def test_detect_pdf(self):
        """Test PDF detection by magic bytes."""
        detector = DocumentDetector()
        assert detector.detect(b"%PDF-1.4 test", "test.pdf") == DocumentType.PDF
        assert detector.detect(b"%PDF content", "test.PDF") == DocumentType.PDF
    
    def test_detect_xlsx(self):
        """Test XLSX detection."""
        detector = DocumentDetector()
        assert detector.detect(b"PK\x03\x04", "test.xlsx") == DocumentType.XLSX
        assert detector.detect(b"PK\x03\x04", "test.xlsm") == DocumentType.XLSX
    
    def test_detect_csv(self):
        """Test CSV detection."""
        detector = DocumentDetector()
        assert detector.detect(b"col1,col2\n1,2", "test.csv") == DocumentType.CSV
        assert detector.detect(b"a,b\n1,2", "test.CSV") == DocumentType.CSV
    
    def test_detect_json(self):
        """Test JSON detection."""
        detector = DocumentDetector()
        assert detector.detect(b'{"key": "value"}', "test.json") == DocumentType.JSON
        assert detector.detect(b'{"a": 1}', "test.JSON") == DocumentType.JSON
    
    def test_detect_html(self):
        """Test HTML detection."""
        detector = DocumentDetector()
        assert detector.detect(b"<html><body>test</body></html>", "test.html") == DocumentType.HTML
        assert detector.detect(b"<HTML>content</HTML>", "test.HTML") == DocumentType.HTML
        assert detector.detect(b"<div>test</div>", "test.xml") == DocumentType.XML
    
    def test_detect_by_extension(self):
        """Test detection by file extension."""
        detector = DocumentDetector()
        assert detector.detect(b"content", "test.txt") == DocumentType.TXT
        assert detector.detect(b"content", "test.xml") == DocumentType.XML


class TestFinancialStatementParser:
    """Tests for FinancialStatementParser."""
    
    def test_identify_income_statement(self):
        """Test identification of income statement."""
        parser = FinancialStatementParser()
        
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Revenue", "1,000,000", "900,000"],
                ["Net Income", "100,000", "80,000"],
                ["Gross Profit", "400,000", "350,000"]
            ]
        )
        
        stmt_type = parser.identify_statement_type(table)
        assert stmt_type == FinancialStatementType.INCOME_STATEMENT
    
    def test_identify_balance_sheet(self):
        """Test identification of balance sheet."""
        parser = FinancialStatementParser()
        
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Total Assets", "5,000,000", "4,500,000"],
                ["Total Liabilities", "2,000,000", "1,800,000"],
                ["Total Equity", "3,000,000", "2,700,000"]
            ]
        )
        
        stmt_type = parser.identify_statement_type(table)
        assert stmt_type == FinancialStatementType.BALANCE_SHEET
    
    def test_identify_cash_flow(self):
        """Test identification of cash flow statement."""
        parser = FinancialStatementParser()
        
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Operating Cash Flow", "500,000", "450,000"],
                ["Investing Cash Flow", "-200,000", "-150,000"],
                ["Financing Cash Flow", "-100,000", "-50,000"]
            ]
        )
        
        stmt_type = parser.identify_statement_type(table)
        assert stmt_type == FinancialStatementType.CASH_FLOW
    
    def test_parse_indonesian_numbers(self):
        """Test parsing Indonesian number formats."""
        parser = FinancialStatementParser()
        
        # Indonesian format: dot as thousands separator, comma as decimal
        assert parser._parse_numeric_value("1.000.000") == 1000000.0
        assert parser._parse_numeric_value("1.000.000,50") == 1000000.5
        assert parser._parse_numeric_value("100.000") == 100000.0
        
        # Standard format
        assert parser._parse_numeric_value("1,000,000") == 1000000.0
        assert parser._parse_numeric_value("1,000,000.50") == 1000000.5
        
        # Parentheses for negative
        assert parser._parse_numeric_value("(100,000)") == -100000.0
        assert parser._parse_numeric_value("(1.000,50)") == -1000.5
    
    def test_parse_income_statement(self):
        """Test parsing income statement into facts."""
        parser = FinancialStatementParser()
        
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Revenue", "1,000,000", "900,000"],
                ["Cost of Goods Sold", "600,000", "550,000"],
                ["Gross Profit", "400,000", "350,000"],
                ["Operating Expenses", "200,000", "180,000"],
                ["Operating Income", "200,000", "170,000"],
                ["Net Income", "150,000", "120,000"]
            ]
        )
        
        facts = parser.parse_statement(table, FinancialStatementType.INCOME_STATEMENT, "2023-FY")
        
        assert len(facts) == 6
        
        revenue_fact = next(f for f in facts if f.concept == "Revenue")
        assert revenue_fact.value == 1000000.0
        assert revenue_fact.unit == "IDR"
        assert revenue_fact.period == "2023-FY"
        assert revenue_fact.statement_type == FinancialStatementType.INCOME_STATEMENT
    
    def test_parse_balance_sheet(self):
        """Test parsing balance sheet into facts."""
        parser = FinancialStatementParser()
        
        table = ExtractedTable(
            headers=["Account", "2023", "2022"],
            rows=[
                ["Total Assets", "5,000,000", "4,500,000"],
                ["Total Liabilities", "2,000,000", "1,800,000"],
                ["Total Equity", "3,000,000", "2,700,000"],
                ["Cash and Cash Equivalents", "500,000", "400,000"]
            ]
        )
        
        facts = parser.parse_statement(table, FinancialStatementType.BALANCE_SHEET, "2023-12-31")
        
        assert len(facts) == 4
        
        assets_fact = next(f for f in facts if f.concept == "Total Assets")
        assert assets_fact.value == 5000000.0
        assert assets_fact.unit == "IDR"
        
        # Check unit detection
        cash_fact = next(f for f in facts if f.concept == "Cash and Cash Equivalents")
        assert cash_fact.unit == "IDR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
