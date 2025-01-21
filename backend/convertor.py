import osmium

class OsmPbfToXmlHandler(osmium.SimpleHandler):
    def __init__(self, output_file):
        super().__init__()
        self.output_file = output_file
        self.writer = osmium.SimpleWriter(output_file)

    def node(self, n):
        self.writer.add_node(n)

    def way(self, w):
        self.writer.add_way(w)

    def relation(self, r):
        self.writer.add_relation(r)

    def close(self):
        self.writer.close()

def convert_pbf_to_osm(input_file, output_file):
    print(f"Starting conversion: {input_file} to {output_file}")
    handler = OsmPbfToXmlHandler(output_file)
    handler.apply_file(input_file)
    handler.close()
    print(f"Conversion complete! Saved as {output_file}")

# Update paths to absolute paths
input_pbf_file = r"C:\Users\raj37\Gravity model python_with backend\backend\india-latest.osm.pbf"  # Full path to the .osm.pbf file
output_osm_file = r"C:\Users\raj37\Gravity model python_with backend\backend\india-latest.osm"    # Full path to the .osm file

convert_pbf_to_osm(input_pbf_file, output_osm_file)
