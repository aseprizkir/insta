import csv
import os

class BotExporter:
    @staticmethod
    def export_connections_csv(username, relation, connections, output_dir="exports"):
        """Mengekspor list followers/following ke CSV."""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{username}_{relation}.csv"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["No", "User ID", "Username", "Full Name"])
                for idx, c in enumerate(connections, 1):
                    writer.writerow([idx, c.get("id"), f"@{c.get('username')}", c.get("fullname")])
            return filepath
        except Exception as e:
            raise Exception(f"Gagal ekspor CSV: {str(e)}")

    @staticmethod
    def export_comments_csv(post_id, comments, output_dir="exports"):
        """Mengekspor komentar ke CSV."""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"comments_{post_id}.csv"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["No", "Comment ID", "Username", "Full Name", "Comment Text", "Timestamp UTC"])
                for idx, c in enumerate(comments, 1):
                    writer.writerow([
                        idx, 
                        c.get("comment_id"), 
                        f"@{c.get('username')}", 
                        c.get("fullname"), 
                        c.get("text"), 
                        c.get("created_at")
                    ])
            return filepath
        except Exception as e:
            raise Exception(f"Gagal ekspor CSV: {str(e)}")

    @staticmethod
    def export_report_txt(title, content, output_dir="exports"):
        """Mengekspor laporan analisis AI ke file teks."""
        os.makedirs(output_dir, exist_ok=True)
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        filename = f"report_{safe_title}.txt"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, mode='w', encoding='utf-8') as f:
                f.write(content)
            return filepath
        except Exception as e:
            raise Exception(f"Gagal ekspor laporan: {str(e)}")
