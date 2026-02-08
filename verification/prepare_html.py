
import os

template_path = "Deendayal_botz/template/req.html"
output_path = "verification/test_req.html"

with open(template_path, "r") as f:
    content = f.read()

# Replace placeholders with dummy data
content = content.replace("{{file_name}}", "Test Movie 2025")
# Use a sample video URL or local file if needed, but a remote one is fine for layout check
content = content.replace("{{file_url}}", "https://cdn.plyr.io/static/demo/View_From_A_Blue_Moon_Trailer-576p.mp4")

with open(output_path, "w") as f:
    f.write(content)

print(f"Created {output_path}")
