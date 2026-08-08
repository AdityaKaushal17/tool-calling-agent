CREATE ROLE tool_agent_readonly LOGIN PASSWORD 'tool_agent_readonly';
GRANT CONNECT ON DATABASE tool_agent TO tool_agent_readonly;
GRANT USAGE ON SCHEMA public TO tool_agent_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE tool_agent IN SCHEMA public GRANT SELECT ON TABLES TO tool_agent_readonly;
