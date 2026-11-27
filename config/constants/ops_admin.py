"""Dedicated Ops Admin investigation runtime configuration."""

OPS_ADMIN_PROFILE_ENV = "OPENSRE_AGENT_PROFILE"
OPS_ADMIN_READONLY_PROFILE = "ops-admin-readonly"
OPS_ADMIN_INVESTIGATOR_PROFILE = "sre-investigator-v1"
OPS_ADMIN_URL_ENV = "OPS_ADMIN_URL"
OPS_ADMIN_TIMEOUT_SECONDS_ENV = "OPS_ADMIN_TIMEOUT_SECONDS"
OPS_ADMIN_SERVICE_ID_ENV = "OPS_ADMIN_SERVICE_ID"
OPS_ADMIN_QUERY_ENDPOINTS = {
    "ops_admin_list_alerts": "alerts",
    "ops_admin_query_metrics": "metrics",
    "ops_admin_query_logs": "logs",
    "ops_admin_get_resource_status": "resource-status",
    "ops_admin_list_changes": "changes",
    "ops_admin_query_traces": "traces",
    "ops_admin_search_runbooks": "runbooks",
}
OPS_ADMIN_PROPOSAL_TOOL = "ops_admin_create_action_proposal"
OPS_ADMIN_MAX_RESPONSE_BYTES = 262144

OPS_ADMIN_MCP_ENABLED_ENV = "OPS_ADMIN_MCP_ENABLED"
OPS_ADMIN_MCP_SERVICE_TOKEN_ENV = "OPS_ADMIN_OPENSRE_SERVICE_TOKEN"
OPS_ADMIN_MCP_CREDENTIAL_PREFIX = "OPS_ADMIN_MCP_"
