"""
ERIN AI Intelligence - Autonomous Knowledge Base
Persistent knowledge graph connecting companies, securities, financials, indicators, news, and regulations.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Set, Tuple, Union
from collections import defaultdict

import structlog

logger = structlog.get_logger(__name__)


class EntityType(str, Enum):
    COMPANY = "company"
    SECURITY = "security"
    INDUSTRY = "industry"
    FINANCIAL_STATEMENT = "financial_statement"
    ECONOMIC_INDICATOR = "economic_indicator"
    NEWS_ARTICLE = "news_article"
    CORPORATE_ACTION = "corporate_action"
    REGULATION = "regulation"
    RESEARCH_REPORT = "research_report"
    PERSON = "person"
    LOCATION = "location"


class RelationType(str, Enum):
    OWNS = "owns"
    ISSUED_BY = "issued_by"
    BELONGS_TO = "belongs_to"
    HAS_FINANCIALS = "has_financials"
    HAS_INDICATOR = "has_indicator"
    MENTIONS = "mentions"
    TRIGGERED_BY = "triggered_by"
    REGULATES = "regulates"
    COMPETES_WITH = "competes_with"
    SUBSIDIARY_OF = "subsidiary_of"
    PARTNERSHIP_WITH = "partnership_with"
    AUDITED_BY = "audited_by"


@dataclass
class KnowledgeEntity:
    """An entity in the knowledge graph."""
    entity_type: EntityType
    name: str
    entity_id: str = field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:12]}")
    aliases: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None
    source_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class KnowledgeRelation:
    """A relation between entities in the knowledge graph."""
    source_entity_id: str
    target_entity_id: str
    relation_type: RelationType
    relation_id: str = field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:12]}")
    properties: Dict[str, Any] = field(default_factory=dict)
    valid_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None
    source_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TemporalFact:
    """A fact with temporal validity."""
    entity_id: str
    attribute: str
    value: Any
    valid_from: datetime
    fact_id: str = field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:12]}")
    valid_to: Optional[datetime] = None
    source_id: str = ""
    confidence: float = 1.0
    provenance: Dict[str, Any] = field(default_factory=dict)


class KnowledgeBase:
    """Persistent financial knowledge base with temporal validity."""
    
    def __init__(self, db_path: str = "~/.erin/data/knowledge.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._entity_cache: Dict[str, KnowledgeEntity] = {}
        self._relation_cache: Dict[str, List[KnowledgeRelation]] = defaultdict(list)
        self._type_index: Dict[EntityType, Set[str]] = defaultdict(set)
        self._name_index: Dict[str, Set[str]] = defaultdict(set)
    
    async def initialize(self):
        """Initialize the knowledge base database."""
        if self._initialized:
            return
        
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    aliases TEXT,
                    properties TEXT,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    source_ids TEXT,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_valid ON entities(valid_from, valid_to)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    properties TEXT,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    source_ids TEXT,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_entity_id) REFERENCES entities(entity_id),
                    FOREIGN KEY (target_entity_id) REFERENCES entities(entity_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_entity_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_entity_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type)
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS temporal_facts (
                    fact_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    attribute TEXT NOT NULL,
                    value TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    source_id TEXT,
                    confidence REAL DEFAULT 1.0,
                    provenance TEXT
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_entity ON temporal_facts(entity_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_attribute ON temporal_facts(attribute)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_valid ON temporal_facts(valid_from, valid_to)
            """)
            
            await db.commit()
        
        await self._load_cache()
        self._initialized = True
        logger.info("Knowledge base initialized", entities=len(self._entity_cache))
    
    async def _load_cache(self):
        """Load entities and relations into memory cache."""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("SELECT * FROM entities") as cursor:
                async for row in cursor:
                    entity = KnowledgeEntity(
                        entity_id=row["entity_id"],
                        entity_type=EntityType(row["entity_type"]),
                        name=row["name"],
                        aliases=json.loads(row["aliases"]) if row["aliases"] else [],
                        properties=json.loads(row["properties"]) if row["properties"] else {},
                        valid_from=datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00")),
                        valid_to=datetime.fromisoformat(row["valid_to"].replace("Z", "+00:00")) if row["valid_to"] else None,
                        source_ids=json.loads(row["source_ids"]) if row["source_ids"] else [],
                        confidence=row["confidence"],
                        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                    )
                    self._entity_cache[entity.entity_id] = entity
                    self._type_index[entity.entity_type].add(entity.entity_id)
                    self._name_index[entity.name.lower()].add(entity.entity_id)
                    for alias in entity.aliases:
                        self._name_index[alias.lower()].add(entity.entity_id)
            
            async with db.execute("SELECT * FROM relations") as cursor:
                async for row in cursor:
                    relation = KnowledgeRelation(
                        relation_id=row["relation_id"],
                        source_entity_id=row["source_entity_id"],
                        target_entity_id=row["target_entity_id"],
                        relation_type=RelationType(row["relation_type"]),
                        properties=json.loads(row["properties"]) if row["properties"] else {},
                        valid_from=datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00")),
                        valid_to=datetime.fromisoformat(row["valid_to"].replace("Z", "+00:00")) if row["valid_to"] else None,
                        source_ids=json.loads(row["source_ids"]) if row["source_ids"] else [],
                        confidence=row["confidence"],
                        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                    )
                    self._relation_cache[relation.source_entity_id].append(relation)
    
    def _entity_to_row(self, entity: KnowledgeEntity) -> tuple:
        return (
            entity.entity_id, entity.entity_type.value, entity.name,
            json.dumps(entity.aliases), json.dumps(entity.properties),
            entity.valid_from.isoformat(),
            entity.valid_to.isoformat() if entity.valid_to else None,
            json.dumps(entity.source_ids), entity.confidence,
            entity.created_at.isoformat(), entity.updated_at.isoformat()
        )
    
    def _relation_to_row(self, relation: KnowledgeRelation) -> tuple:
        return (
            relation.relation_id, relation.source_entity_id, relation.target_entity_id,
            relation.relation_type.value, json.dumps(relation.properties),
            relation.valid_from.isoformat(),
            relation.valid_to.isoformat() if relation.valid_to else None,
            json.dumps(relation.source_ids), relation.confidence,
            relation.created_at.isoformat()
        )
    
    # Entity operations
    async def add_entity(self, entity: KnowledgeEntity) -> KnowledgeEntity:
        """Add an entity to the knowledge base."""
        if not self._initialized:
            await self.initialize()
        
        entity.updated_at = datetime.now(timezone.utc)
        
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._entity_to_row(entity))
            await db.commit()
        
        # Update cache
        if entity.entity_id in self._entity_cache:
            old = self._entity_cache[entity.entity_id]
            self._name_index[old.name.lower()].discard(entity.entity_id)
            for alias in old.aliases:
                self._name_index[alias.lower()].discard(entity.entity_id)
        
        self._entity_cache[entity.entity_id] = entity
        self._type_index[entity.entity_type].add(entity.entity_id)
        self._name_index[entity.name.lower()].add(entity.entity_id)
        for alias in entity.aliases:
            self._name_index[alias.lower()].add(entity.entity_id)
        
        logger.info("Entity added", entity_id=entity.entity_id, type=entity.entity_type.value, name=entity.name)
        return entity
    
    async def get_entity(self, entity_id: str) -> Optional[KnowledgeEntity]:
        """Get an entity by ID."""
        if not self._initialized:
            await self.initialize()
        return self._entity_cache.get(entity_id)
    
    async def find_entities(self, name: str, entity_type: Optional[EntityType] = None) -> List[KnowledgeEntity]:
        """Find entities by name (supports partial matching)."""
        if not self._initialized:
            await self.initialize()
        
        name_lower = name.lower()
        candidate_ids = set()
        
        for indexed_name, ids in self._name_index.items():
            if name_lower in indexed_name or indexed_name in name_lower:
                candidate_ids.update(ids)
        
        entities = [self._entity_cache[eid] for eid in candidate_ids if eid in self._entity_cache]
        
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        
        return entities
    
    async def get_entities_by_type(self, entity_type: EntityType, limit: int = 1000) -> List[KnowledgeEntity]:
        """Get all entities of a specific type."""
        if not self._initialized:
            await self.initialize()
        
        ids = list(self._type_index.get(entity_type, set()))[:limit]
        return [self._entity_cache[eid] for eid in ids if eid in self._entity_cache]
    
    # Relation operations
    async def add_relation(self, relation: KnowledgeRelation) -> KnowledgeRelation:
        """Add a relation between entities."""
        if not self._initialized:
            await self.initialize()
        
        # Verify both entities exist
        if relation.source_entity_id not in self._entity_cache:
            raise ValueError(f"Source entity not found: {relation.source_entity_id}")
        if relation.target_entity_id not in self._entity_cache:
            raise ValueError(f"Target entity not found: {relation.target_entity_id}")
        
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._relation_to_row(relation))
            await db.commit()
        
        self._relation_cache[relation.source_entity_id].append(relation)
        logger.info("Relation added", relation_id=relation.relation_id, type=relation.relation_type.value)
        return relation
    
    async def get_relations(self, entity_id: str, relation_type: Optional[RelationType] = None, direction: str = "outgoing") -> List[KnowledgeRelation]:
        """Get relations for an entity."""
        if not self._initialized:
            await self.initialize()
        
        relations = []
        
        if direction in ["outgoing", "both"]:
            for rel in self._relation_cache.get(entity_id, []):
                if relation_type is None or rel.relation_type == relation_type:
                    relations.append(rel)
        
        if direction in ["incoming", "both"]:
            for rels in self._relation_cache.values():
                for rel in rels:
                    if rel.target_entity_id == entity_id and (relation_type is None or rel.relation_type == relation_type):
                        relations.append(rel)
        
        return relations
    
    # Temporal facts
    async def add_temporal_fact(self, fact: TemporalFact) -> TemporalFact:
        """Add a temporal fact."""
        if not self._initialized:
            await self.initialize()
        
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO temporal_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fact.fact_id, fact.entity_id, fact.attribute, json.dumps(fact.value),
                fact.valid_from.isoformat(),
                fact.valid_to.isoformat() if fact.valid_to else None,
                fact.source_id, fact.confidence, json.dumps(fact.provenance)
            ))
            await db.commit()
        
        return fact
    
    async def get_temporal_facts(self, entity_id: str, attribute: Optional[str] = None, at_time: Optional[datetime] = None) -> List[TemporalFact]:
        """Get temporal facts for an entity, optionally at a specific point in time."""
        if not self._initialized:
            await self.initialize()
        
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = "SELECT * FROM temporal_facts WHERE entity_id = ?"
            params = [entity_id]
            
            if attribute:
                query += " AND attribute = ?"
                params.append(attribute)
            
            if at_time:
                query += " AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)"
                params.extend([at_time.isoformat(), at_time.isoformat()])
            
            query += " ORDER BY valid_from DESC"
            
            facts = []
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    facts.append(TemporalFact(
                        fact_id=row["fact_id"],
                        entity_id=row["entity_id"],
                        attribute=row["attribute"],
                        value=json.loads(row["value"]),
                        valid_from=datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00")),
                        valid_to=datetime.fromisoformat(row["valid_to"].replace("Z", "+00:00")) if row["valid_to"] else None,
                        source_id=row["source_id"] or "",
                        confidence=row["confidence"],
                        provenance=json.loads(row["provenance"]) if row["provenance"] else {}
                    ))
            return facts
    
    # Temporal queries
    async def get_entity_at_time(self, entity_id: str, at_time: datetime) -> Optional[Dict[str, Any]]:
        """Get entity state at a specific point in time."""
        entity = await self.get_entity(entity_id)
        if not entity or entity.valid_from > at_time or (entity.valid_to and entity.valid_to <= at_time):
            return None
        
        facts = await self.get_temporal_facts(entity_id, at_time=at_time)
        state = {
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "properties": entity.properties.copy()
        }
        
        for fact in facts:
            state[fact.attribute] = fact.value
        
        return state
    
    # Graph queries
    async def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> List[List[KnowledgeRelation]]:
        """Find paths between two entities (BFS)."""
        if not self._initialized:
            await self.initialize()
        
        if source_id == target_id:
            return [[]]
        
        queue = [(source_id, [])]
        visited = {source_id}
        paths = []
        
        while queue and len(paths) < 10:
            current_id, path = queue.pop(0)
            
            if len(path) >= max_depth:
                continue
            
            relations = await self.get_relations(current_id)
            for rel in relations:
                if rel.target_entity_id == target_id:
                    paths.append(path + [rel])
                elif rel.target_entity_id not in visited:
                    visited.add(rel.target_entity_id)
                    queue.append((rel.target_entity_id, path + [rel]))
        
        return paths
    
    async def get_neighbors(self, entity_id: str, max_depth: int = 1) -> Dict[str, List[KnowledgeEntity]]:
        """Get neighboring entities up to max_depth."""
        if not self._initialized:
            await self.initialize()
        
        neighbors = defaultdict(list)
        current_level = {entity_id}
        visited = {entity_id}
        
        for depth in range(1, max_depth + 1):
            next_level = set()
            for eid in current_level:
                relations = await self.get_relations(eid)
                for rel in relations:
                    if rel.target_entity_id not in visited:
                        target = await self.get_entity(rel.target_entity_id)
                        if target:
                            neighbors[f"depth_{depth}"].append(target)
                            next_level.add(rel.target_entity_id)
                            visited.add(rel.target_entity_id)
            current_level = next_level
            if not current_level:
                break
        
        return dict(neighbors)
    
    # Search
    async def search(self, query: str, entity_types: Optional[List[EntityType]] = None, limit: int = 50) -> List[KnowledgeEntity]:
        """Full-text search across entities."""
        if not self._initialized:
            await self.initialize()
        
        query_lower = query.lower()
        results = []
        
        for entity in self._entity_cache.values():
            if entity_types and entity.entity_type not in entity_types:
                continue
            
            score = 0
            if query_lower in entity.name.lower():
                score += 10
            for alias in entity.aliases:
                if query_lower in alias.lower():
                    score += 5
            for key, value in entity.properties.items():
                if query_lower in str(value).lower():
                    score += 1
            
            if score > 0:
                results.append((score, entity))
        
        results.sort(key=lambda x: -x[0])
        return [e for _, e in results[:limit]]
    
    # Statistics
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        if not self._initialized:
            await self.initialize()
        
        by_type = {}
        for etype, ids in self._type_index.items():
            by_type[etype.value] = len(ids)
        
        relation_count = sum(len(rels) for rels in self._relation_cache.values())
        
        return {
            "total_entities": len(self._entity_cache),
            "total_relations": relation_count,
            "by_type": by_type
        }
    
    # Company/Security specific helpers
    async def create_company(self, name: str, cik: str = "", tickers: Dict[str, str] = None, **kwargs) -> KnowledgeEntity:
        """Create a company entity."""
        entity = KnowledgeEntity(
            entity_type=EntityType.COMPANY,
            name=name,
            properties={
                "cik": cik,
                "tickers": tickers or {},
                **kwargs
            }
        )
        return await self.add_entity(entity)
    
    async def create_security(self, symbol: str, figi: str = "", company_id: str = "", **kwargs) -> KnowledgeEntity:
        """Create a security entity and link to company."""
        entity = KnowledgeEntity(
            entity_type=EntityType.SECURITY,
            name=symbol,
            properties={
                "figi": figi,
                "symbol": symbol,
                **kwargs
            }
        )
        entity = await self.add_entity(entity)
        
        if company_id:
            await self.add_relation(KnowledgeRelation(
                source_entity_id=entity.entity_id,
                target_entity_id=company_id,
                relation_type=RelationType.ISSUED_BY
            ))
        
        return entity
    
    async def link_financials(self, company_id: str, statement_type: str, period: str, facts: List[Dict[str, Any]], source_id: str) -> List[TemporalFact]:
        """Link financial facts to a company."""
        temporal_facts = []
        for fact in facts:
            tf = TemporalFact(
                entity_id=company_id,
                attribute=f"{statement_type}.{fact.get('concept', 'unknown')}",
                value=fact.get('value'),
                valid_from=datetime.fromisoformat(period.replace("Z", "+00:00")) if "T" in period else datetime.now(timezone.utc),
                source_id=source_id,
                provenance={"statement_type": statement_type, "period": period}
            )
            temporal_facts.append(await self.add_temporal_fact(tf))
        return temporal_facts


# Global instance
_knowledge_base: Optional[KnowledgeBase] = None


async def get_knowledge_base() -> KnowledgeBase:
    """Get or create the global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        await _knowledge_base.initialize()
    return _knowledge_base


if __name__ == "__main__":
    async def test():
        kb = KnowledgeBase("/tmp/test_kb.db")
        await kb.initialize()
        
        # Create company
        company = await kb.create_company(
            "PT Bank Central Asia Tbk",
            cik="",
            tickers={"IDX": "BBCA"},
            sector="Banking",
            country="ID"
        )
        print(f"Created company: {company.name} ({company.entity_id})")
        
        # Create security
        security = await kb.create_security(
            "BBCA",
            figi="BBG000B9XRY4",
            company_id=company.entity_id,
            asset_class="EQUITY",
            currency="IDR"
        )
        print(f"Created security: {security.name} ({security.entity_id})")
        
        # Add financial facts
        facts = [
            {"concept": "Total Assets", "value": 1500000000000000},
            {"concept": "Net Income", "value": 40000000000000},
        ]
        await kb.link_financials(company.entity_id, "balance_sheet", "2023-12-31", facts, "idx_financials")
        print("Added financial facts")
        
        # Temporal query
        state = await kb.get_entity_at_time(company.entity_id, datetime.now(timezone.utc))
        print(f"Company state keys: {list(state.keys()) if state else 'None'}")
        
        # Search
        results = await kb.search("Bank Central Asia")
        print(f"Search results: {len(results)}")
        
        # Stats
        stats = await kb.get_stats()
        print(f"Stats: {stats}")
        
        print("\nKnowledge base tests passed!")
    
    import asyncio
    asyncio.run(test())
