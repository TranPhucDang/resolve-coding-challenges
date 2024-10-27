from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import Client
from diagrams.onprem.compute import Server
from diagrams.onprem.database import Mongodb
from diagrams.onprem.inmemory import Redis

with Diagram("Real-Time Quiz System Architecture", show=False):
    client = Client("User")

    with Cluster("Server"):
        webapp = Server("FastAPI App")
        websocket = Server("WebSocket")
    
    db = Mongodb("MongoDB")
    cache = Redis("Redis")

    client >> Edge(label="Join Quiz / Submit Answers") >> webapp
    webapp >> Edge(label="Validate Quiz ID / Save Answer") >> db
    webapp >> Edge(label="Leaderboard Data") >> cache
    websocket >> Edge(label="Broadcast Leaderboard Updates") >> client
