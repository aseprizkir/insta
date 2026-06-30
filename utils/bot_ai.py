import json
from openai import OpenAI

class InstagramAI:
    def __init__(self, api_key=None, base_url=None, model=None):
        # Fallback defaults biar gak nyangkut
        self.api_key = api_key or "sk-placeholder"
        self.base_url = base_url or "https://router.bynara.id/v1"
        self.model = model or "mimo-v2.5-pro-free"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_comments(self, comments):
        """Menganalisis list komentar secara ringkas (sentimen & spam/buzzer)."""
        if not comments:
            return "Tidak ada komentar untuk dianalisis."

        # Format komentar untuk dikirim ke prompt AI (batasi 60 komentar teratas)
        formatted_comments = []
        for i, c in enumerate(comments[:60], 1):
            formatted_comments.append(f"{i}. @{c['username']}: {c['text']}")

        comments_text = "\n".join(formatted_comments)

        prompt = f"""
        Kamu adalah AI yang bertugas menganalisis komentar media sosial target secara singkat dan padat.
        Berikut adalah daftar komentar dari postingan Instagram:

        {comments_text}

        Tolong berikan laporan analisis singkat dalam bahasa Indonesia yang gaul, santai, dan langsung to-the-point:
        1. **Analisis Sentimen Singkat**: Rangkum suasana/sentimen komentar (Positif/Negatif/Netral beserta persentase perkiraan).
        2. **Deteksi Spam / Buzzer / Bot**: Identifikasi akun-akun yang melakukan spamming komentar berulang, menggunakan kata-kata yang sama/senada secara mencurigakan, atau memiliki indikasi buzzer/bot. **Analisis secara adil**: ingat bahwa buzzer tidak hanya menjelek-jelekkan/menyerang (buzzer negatif), tapi bisa juga berupa akun bayaran/fanbase yang memuji-muji secara berlebihan/hasing dengan pola seragam untuk menggiring opini positif (buzzer positif/paid hype).

        Pastikan respons Anda sangat ringkas, padat, dan rapi menggunakan Markdown.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Kamu adalah asisten AI penganalisis komentar media sosial yang praktis dan to-the-point."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ Gagal melakukan analisis AI: {str(e)}"
