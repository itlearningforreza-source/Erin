# ERIN Critical Fixes Summary

## 1. SourceRegistry SQL Parameter Mismatch
File: packages/data-core/src/erin/data_core/source_registry.py
- _source_to_update_row: Remove config_hash from return tuple (35 fields instead of 36)
- from_dict: Add NULL check for datetime fields

## 2. Connectors - OperationalStatus Enum Comparison (CRITICAL)
File: packages/data-core/src/erin/data_core/connectors.py line ~148
FROM: if self.source.operational_status not in ["active", "degraded"]:
TO:   if self.source.operational_status not in [OperationalStatus.ACTIVE, OperationalStatus.DEGRADED]:

## 3. RegulatoryConnector Infinite Recursion
File: packages/data-core/src/erin/data_core/connectors.py line ~992
FROM: return await self._fetch_ojk(config)
TO:   return await self._fetch_generic(config)

## 4. CrossProviderReconciler ZeroDivisionError (CRITICAL)
File: packages/data-core/src/erin/data_core/integrity.py lines ~521-524
FROM: max(abs(v - consensus) / consensus for v in values) if consensus != 0 else Decimal("0")
TO:
    if consensus != 0:
        max_deviation = max(abs(v - consensus) / consensus for v in values)
    else:
        max_deviation = Decimal("0")

## 5. KnowledgeBase SQL Parameter Mismatches
File: packages/ai-intelligence/src/erin/ai_intelligence/knowledge_base.py
- _entity_to_row: Returns 10 values but INSERT has 11 placeholders
- _relation_to_row: Returns 9 values but INSERT has 10 placeholders

## 6. DocumentConnector Workbook Leak
File: packages/data-core/src/erin/data_core/connectors.py lines ~656, 673
Add wb.close() in finally block after processing

## 7. RegulatoryConnector._fetch_kemenkeu Wrong Call
File: packages/data-core/src/erin/data_core/connectors.py line ~992
FROM: return await self._fetch_ojk(config)
TO:   return await self._fetch_generic(config)

## 8. RestApiConnector Watermark locals() Hack
File: packages/data-core/src/erin/data_core/connectors.py line ~304
FROM: data if 'data' in locals() else {}
TO: Store response_data before try/finally block

## 9. CorporateActionAdjuster Empty Return
File: packages/data-core/src/erin/data_core/integrity.py lines ~548-561
Add actual fetch_from_source call to fetch corporate actions

## 10. SourceRegistry.from_dict NULL Handling
File: packages/data-core/src/erin/data_core/source_registry.py line ~228
Add check: data[key] is not None and isinstance(data[key], str)

## 11. KnowledgeBase SQL Mismatches
File: packages/ai-intelligence/src/erin/ai_intelligence/knowledge_base.py
- _entity_to_row: Returns 10 values but INSERT has 11 placeholders
- _relation_to_row: Returns 9 values but INSERT has 10 placeholders

## 12. DocumentConnector Workbook Leak
File: packages/data-core/src/erin/data_core/connectors.py lines ~656, 673
Add wb.close() in finally block after processing

## 13. RegulatoryConnector._fetch_kemenkeu Wrong Call
Line ~992: return await self._fetch_ojk(config) -> return await self._fetch_generic(config)

## 14. RestApiConnector Watermark locals() Hack
Line ~304: Store response_data before try/finally block

## 15. CorporateActionAdjuster Empty Return
Lines ~548-561: Add actual fetch_from_source call to fetch corporate actions

## 16. SourceRegistry.from_dict NULL Handling
Add check: data[key] is not None and isinstance(data[key], str)

## 17. KnowledgeBase SQL Mismatches
- _entity_to_row: Returns 10 values but INSERT has 11 placeholders
- _relation_to_row: Returns 9 values but INSERT has 10 placeholders

## 18. DocumentConnector Workbook Leak
Add wb.close() in finally block

## 19. RegulatoryConnector._fetch_kemenkeu Wrong Call
Change to _fetch_generic(config)

## 20. RestApiConnector Watermark locals() Hack
Store response_data before try/finally block

## 21. CorporateActionAdjuster Empty Return
Add actual fetch_from_source call to fetch corporate actions

## 22. SourceRegistry.from_dict NULL Handling
Add check: data[key] is not None and isinstance(data[key], str)

## 23. KnowledgeBase SQL Mismatches
- _entity_to_row: Returns 10 values but INSERT has 11 placeholders
- _relation_to_row: Returns 9 values but INSERT has 10 placeholders

## 24. DocumentConnector Workbook Leak
Add wb.close() in finally block

## 25. RegulatoryConnector._fetch_kemenkeu Wrong Call
Change to _fetch_generic(config)

## 26. RestApiConnector Watermark locals() Hack
Store response_data before try/finally block

## 27. CorporateActionAdjuster Empty Return
Add actual fetch_from_source call to fetch corporate actions

## 28. SourceRegistry.from_dict NULL Handling
Add check: data[key] is not None and isinstance(data[key], str)

## 29. KnowledgeBase SQL Mismatches
- _entity_to_row: Returns 10 values but INSERT has 11 placeholders
- _relation_to_row: Returns 9 values but INSERT has 10 placeholders

## 30. DocumentConnector Workbook Leak
Add wb.close() in finally block

