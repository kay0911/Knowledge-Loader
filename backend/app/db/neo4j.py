from neo4j import GraphDatabase
from app.core.config import settings
from app.core.logging import logger

class Neo4jClient:
    def __init__(self):
        self.driver = None

    def connect(self):
        if self.driver:
            return
        
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USER
        password = settings.NEO4J_PASSWORD
        try:
            logger.info(f"Connecting to Neo4j database at {uri}...")
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connectivity
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j database successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {str(e)}")
            raise e

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None
            logger.info("Closed Neo4j database connection.")

    def get_session(self):
        if not self.driver:
            self.connect()
        return self.driver.session()

neo4j_client = Neo4jClient()
