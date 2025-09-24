"""
Query Handler Application Service

Handles frontend queries for data and system information.
Provides read-only access to system state and historical data.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import logging
import json

from ...domain.value_objects.workflow_state import WorkflowState
from ...domain.entities.hardware import HardwareSystem
from ...domain.services.dataset_repository import (
    StimulusDatasetRepository,
    AcquisitionSessionRepository,
    AnalysisResultRepository,
    SortOrder
)
from ...domain.services.workflow_orchestrator import WorkflowOrchestrator


logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries supported"""
    SYSTEM_STATUS = "system_status"
    WORKFLOW_STATE = "workflow_state"
    HARDWARE_STATUS = "hardware_status"
    DATASET_LIST = "dataset_list"
    SESSION_LIST = "session_list"
    ANALYSIS_LIST = "analysis_list"
    DATASET_DETAILS = "dataset_details"
    SESSION_DETAILS = "session_details"
    ANALYSIS_DETAILS = "analysis_details"
    SYSTEM_LOGS = "system_logs"
    PERFORMANCE_METRICS = "performance_metrics"
    STORAGE_INFO = "storage_info"


class QueryError(Exception):
    """Raised when query handling encounters errors"""
    pass


class QueryHandler:
    """
    Application service for handling frontend queries

    Provides structured read-only access to system state, historical data,
    and performance metrics without exposing internal implementation details.
    """

    def __init__(
        self,
        workflow_orchestrator: WorkflowOrchestrator,
        hardware_system: HardwareSystem,
        stimulus_repo: StimulusDatasetRepository,
        session_repo: AcquisitionSessionRepository,
        analysis_repo: AnalysisResultRepository
    ):
        self.workflow_orchestrator = workflow_orchestrator
        self.hardware_system = hardware_system
        self.stimulus_repo = stimulus_repo
        self.session_repo = session_repo
        self.analysis_repo = analysis_repo

        # Query handlers registry
        self._query_handlers = {
            QueryType.SYSTEM_STATUS: self._handle_system_status_query,
            QueryType.WORKFLOW_STATE: self._handle_workflow_state_query,
            QueryType.HARDWARE_STATUS: self._handle_hardware_status_query,
            QueryType.DATASET_LIST: self._handle_dataset_list_query,
            QueryType.SESSION_LIST: self._handle_session_list_query,
            QueryType.ANALYSIS_LIST: self._handle_analysis_list_query,
            QueryType.DATASET_DETAILS: self._handle_dataset_details_query,
            QueryType.SESSION_DETAILS: self._handle_session_details_query,
            QueryType.ANALYSIS_DETAILS: self._handle_analysis_details_query,
            QueryType.SYSTEM_LOGS: self._handle_system_logs_query,
            QueryType.PERFORMANCE_METRICS: self._handle_performance_metrics_query,
            QueryType.STORAGE_INFO: self._handle_storage_info_query
        }

        # Query result caching (for expensive queries)
        self._query_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 5.0  # Cache results for 5 seconds

        logger.info("Query handler initialized")

    async def handle_query(
        self,
        query_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle frontend query and return structured response

        Args:
            query_type: Type of query to execute
            parameters: Optional query parameters

        Returns:
            Structured query response
        """
        try:
            # Validate query type
            try:
                query_enum = QueryType(query_type)
            except ValueError:
                raise QueryError(f"Unknown query type: {query_type}")

            # Check cache first
            cache_key = self._generate_cache_key(query_enum, parameters)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.debug(f"Returning cached result for {query_type}")
                return cached_result

            # Execute query
            handler = self._query_handlers[query_enum]
            result = await handler(parameters or {})

            # Structure response
            response = {
                "query_type": query_type,
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "data": result,
                "parameters": parameters
            }

            # Cache result if appropriate
            if self._should_cache_query(query_enum):
                self._cache_result(cache_key, response)

            logger.debug(f"Handled query: {query_type}")
            return response

        except Exception as e:
            logger.exception(f"Error handling query {query_type}")

            error_response = {
                "query_type": query_type,
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e),
                "parameters": parameters
            }

            return error_response

    async def _handle_system_status_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system status query"""

        workflow_status = self.workflow_orchestrator.get_workflow_status()
        hardware_status = self.hardware_system.get_system_status_summary()
        system_ready, ready_issues = self.hardware_system.is_system_ready_for_acquisition()

        return {
            "workflow": workflow_status,
            "hardware": hardware_status,
            "system_ready": system_ready,
            "ready_issues": ready_issues,
            "uptime": self._calculate_system_uptime()
        }

    async def _handle_workflow_state_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow state query"""

        return self.workflow_orchestrator.get_workflow_status()

    async def _handle_hardware_status_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle hardware status query"""

        component_id = params.get("component_id")

        if component_id:
            # Get specific component status
            component = self.hardware_system.get_component(component_id)
            if not component:
                raise QueryError(f"Component {component_id} not found")

            return {
                "component": component.to_dict(),
                "recent_errors": component.get_recent_errors(24),
                "status_history": [
                    {"timestamp": ts.isoformat(), "status": status.value}
                    for ts, status in component.get_status_history(24)
                ]
            }
        else:
            # Get overall hardware status
            return self.hardware_system.get_system_status_summary()

    async def _handle_dataset_list_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dataset list query"""

        sort_order = SortOrder(params.get("sort", "newest_first"))
        limit = params.get("limit", 50)

        datasets = self.stimulus_repo.list_datasets(sort_order, limit)

        return {
            "datasets": [dataset.to_dict() for dataset in datasets],
            "total_count": len(datasets),
            "sort_order": sort_order.value,
            "limit": limit
        }

    async def _handle_session_list_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session list query"""

        sort_order = SortOrder(params.get("sort", "newest_first"))
        limit = params.get("limit", 50)

        sessions = self.session_repo.list_sessions(sort_order, limit)

        return {
            "sessions": [session.to_dict() for session in sessions],
            "total_count": len(sessions),
            "sort_order": sort_order.value,
            "limit": limit
        }

    async def _handle_analysis_list_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis list query"""

        sort_order = SortOrder(params.get("sort", "newest_first"))
        limit = params.get("limit", 50)
        session_id = params.get("session_id")
        dataset_id = params.get("dataset_id")

        if session_id:
            analyses = self.analysis_repo.find_by_session(session_id)
        elif dataset_id:
            analyses = self.analysis_repo.find_by_dataset(dataset_id)
        else:
            analyses = self.analysis_repo.list_analyses(sort_order, limit)

        return {
            "analyses": [analysis.to_dict() for analysis in analyses],
            "total_count": len(analyses),
            "sort_order": sort_order.value,
            "limit": limit,
            "filters": {
                "session_id": session_id,
                "dataset_id": dataset_id
            }
        }

    async def _handle_dataset_details_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dataset details query"""

        dataset_id = params.get("dataset_id")
        if not dataset_id:
            raise QueryError("dataset_id parameter required")

        if not self.stimulus_repo.exists(dataset_id):
            raise QueryError(f"Dataset {dataset_id} not found")

        dataset = self.stimulus_repo.load(dataset_id)

        return {
            "dataset": dataset.to_dict(),
            "file_info": {
                "exists": dataset.data_files_exist(),
                "total_size_mb": dataset.calculate_total_size() / (1024 * 1024),
                "file_count": len(dataset.data_files)
            }
        }

    async def _handle_session_details_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session details query"""

        session_id = params.get("session_id")
        if not session_id:
            raise QueryError("session_id parameter required")

        if not self.session_repo.exists(session_id):
            raise QueryError(f"Session {session_id} not found")

        session = self.session_repo.load(session_id)

        # Find related analyses
        related_analyses = self.analysis_repo.find_by_session(session_id)

        return {
            "session": session.to_dict(),
            "related_analyses": [analysis.to_dict() for analysis in related_analyses],
            "file_info": {
                "exists": session.data_files_exist(),
                "total_size_mb": session.calculate_total_size() / (1024 * 1024),
                "file_count": len(session.data_files)
            }
        }

    async def _handle_analysis_details_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis details query"""

        analysis_id = params.get("analysis_id")
        if not analysis_id:
            raise QueryError("analysis_id parameter required")

        if not self.analysis_repo.exists(analysis_id):
            raise QueryError(f"Analysis {analysis_id} not found")

        analysis = self.analysis_repo.load(analysis_id)

        return {
            "analysis": analysis.to_dict(),
            "file_info": {
                "exists": analysis.data_files_exist(),
                "total_size_mb": analysis.calculate_total_size() / (1024 * 1024),
                "file_count": len(analysis.data_files)
            }
        }

    async def _handle_system_logs_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system logs query"""

        # This would integrate with actual logging system
        # For now, return placeholder structure

        level = params.get("level", "INFO")
        hours = params.get("hours", 24)
        component = params.get("component")

        return {
            "logs": [],  # Would be populated from actual log files
            "filters": {
                "level": level,
                "hours": hours,
                "component": component
            },
            "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "available_components": ["workflow", "hardware", "analysis", "storage"]
        }

    async def _handle_performance_metrics_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle performance metrics query"""

        # This would integrate with actual performance monitoring
        # For now, return basic system metrics

        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_used_gb": disk.used / (1024**3),
                "disk_total_gb": disk.total / (1024**3)
            },
            "hardware_metrics": {
                "components_operational": len(self.hardware_system.get_operational_components()),
                "components_total": len(self.hardware_system._components),
                "health_score": self.hardware_system.calculate_system_health()
            },
            "timestamp": datetime.now().isoformat()
        }

    async def _handle_storage_info_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle storage information query"""

        stimulus_info = self.stimulus_repo.get_storage_info()

        # Get session and analysis storage info
        session_metadata = self.session_repo.list_sessions(limit=1000)
        analysis_metadata = self.analysis_repo.list_analyses(limit=1000)

        total_sessions_mb = sum(
            meta.file_size_bytes for meta in session_metadata
        ) / (1024 * 1024)

        total_analyses_mb = sum(
            meta.file_size_bytes for meta in analysis_metadata
        ) / (1024 * 1024)

        return {
            "stimulus_datasets": stimulus_info,
            "acquisition_sessions": {
                "count": len(session_metadata),
                "total_size_mb": total_sessions_mb
            },
            "analysis_results": {
                "count": len(analysis_metadata),
                "total_size_mb": total_analyses_mb
            },
            "total_size_mb": stimulus_info["total_size_mb"] + total_sessions_mb + total_analyses_mb
        }

    def _generate_cache_key(
        self,
        query_type: QueryType,
        parameters: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for query"""

        param_str = json.dumps(parameters or {}, sort_keys=True)
        return f"{query_type.value}:{param_str}"

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached query result if still valid"""

        if cache_key not in self._query_cache:
            return None

        cached_data = self._query_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data["cached_at"])

        if (datetime.now() - cache_time).total_seconds() > self._cache_ttl_seconds:
            # Cache expired
            del self._query_cache[cache_key]
            return None

        return cached_data["result"]

    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache query result"""

        self._query_cache[cache_key] = {
            "result": result,
            "cached_at": datetime.now().isoformat()
        }

        # Limit cache size
        if len(self._query_cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(
                self._query_cache.keys(),
                key=lambda k: self._query_cache[k]["cached_at"]
            )[:50]

            for key in oldest_keys:
                del self._query_cache[key]

    def _should_cache_query(self, query_type: QueryType) -> bool:
        """Determine if query results should be cached"""

        # Cache expensive queries but not real-time data
        cacheable_queries = {
            QueryType.DATASET_LIST,
            QueryType.SESSION_LIST,
            QueryType.ANALYSIS_LIST,
            QueryType.STORAGE_INFO,
            QueryType.PERFORMANCE_METRICS
        }

        return query_type in cacheable_queries

    def _calculate_system_uptime(self) -> Dict[str, Any]:
        """Calculate system uptime"""

        import psutil

        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        return {
            "boot_time": boot_time.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime).split('.')[0]  # Remove microseconds
        }

    def get_query_stats(self) -> Dict[str, Any]:
        """Get query handler statistics"""

        return {
            "supported_queries": [query_type.value for query_type in QueryType],
            "cache_size": len(self._query_cache),
            "cache_ttl_seconds": self._cache_ttl_seconds
        }