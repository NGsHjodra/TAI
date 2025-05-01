from flask import Flask, jsonify, render_template_string
from threading import Thread

class FlaskVisualizer:
    def __init__(self, community, port=8080):
        self.community = community
        self.port = port
        self.app = Flask(__name__)
        self.known_nodes = {}
        
        # Setup routes
        self.app.add_url_rule('/', 'index', self.get_index)
        self.app.add_url_rule('/topology', 'topology', self.get_topology)
        self.app.add_url_rule('/transactions', 'transactions', self.get_transactions)
        
    def get_topology(self):
        nodes = [{
            'id': self.community.my_peer.mid.hex(),
            'label': self.community.my_peer.mid.hex()[:6],
            'color': 'green'
        }]
        
        links = []
        
        # Add peers and links to the topology
        for peer in self.community.get_peers():
            peer_id = peer.mid.hex()
            nodes.append({
                'id': peer_id,
                'label': peer_id[:6],
                'color': 'blue'
            })
            links.append({
                'source': self.community.my_peer.mid.hex(),
                'target': peer_id,
                'value': 5
            })
            
        return jsonify({'nodes': nodes, 'links': links})
    
    def get_transactions(self):
        return jsonify({'transactions': self.community.transactions[-10:]})
    
    def get_index(self):
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Network Visualizer</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                .node { stroke: #fff; stroke-width: 1.5px; }
                .link { stroke: #999; stroke-opacity: 0.6; }
                body { font-family: Arial; margin: 20px; }
                #graph { border: 1px solid #ddd; border-radius: 5px; }
                .node text {
                    fill: black;
                    font-size: 12px;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <h1>Network Topology</h1>
            <div id="graph"></div>
            <div id="transactions"></div>
            
            <script>
                const width = 800, height = 600;
                const svg = d3.select("#graph")
                    .append("svg")
                    .attr("width", width)
                    .attr("height", height);
                
                const simulation = d3.forceSimulation()
                    .force("link", d3.forceLink().id(d => d.id).distance(100))
                    .force("charge", d3.forceManyBody().strength(-300))
                    .force("center", d3.forceCenter(width / 2, height / 2));
                
                function updateGraph() {
                    fetch('/topology')
                        .then(response => response.json())
                        .then(data => {
                            const {nodes, links} = data;
                            
                            const link = svg.selectAll(".link")
                                .data(links)
                                .join("line")
                                .attr("class", "link");
                            
                            const node = svg.selectAll(".node")
                                .data(nodes)
                                .join("g")
                                .attr("class", "node");
                            
                            node.append("circle")
                                .attr("r", 10)
                                .attr("fill", d => d.color || "#69b3a2");
                            
                            node.append("text")
                                .attr("dy", -15)
                                .attr("fill", "black")  // Force black color
                                .attr("stroke", "none") // Remove any stroke
                                .attr("style", "fill: black !important;") // Nuclear option
                                .attr("text-anchor", "middle")
                                .text(d => d.label || d.id.slice(0,6));
  
                            simulation.nodes(nodes).on("tick", () => {
                                link.attr("x1", d => d.source.x)
                                    .attr("y1", d => d.source.y)
                                    .attr("x2", d => d.target.x)
                                    .attr("y2", d => d.target.y);
                                
                                node.attr("transform", d => `translate(${d.x},${d.y})`);
                            });
                            
                            simulation.force("link").links(links);
                        });
                    
                    fetch('/transactions')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById("transactions").innerHTML = 
                                `<h2>Recent Transactions</h2><ul>${
                                    data.transactions.map(tx => 
                                        `<li>${tx.sender} → ${tx.receiver}: ${tx.amount}</li>`
                                    ).join('')
                                }</ul>`;
                        });
                }
                
                setInterval(updateGraph, 3000);
                updateGraph();
            </script>
        </body>
        </html>
        """)

    def start(self):
        """Run the Flask server on the same port for all routes"""
        self.app.run(host='0.0.0.0', port=self.port, debug=False)
        print(f"Flask visualizer running on http://localhost:{self.port}")
