import os
import openai
import numpy as np
import redis
import argparse


class NoteFinder:
    def __init__(self, folder):
        self.folder = folder
        self.notes = self.load_notes()

    def load_notes(self):
        notes = {}
        for filename in os.listdir(self.folder):
            if filename.endswith(".md"):
                with open(os.path.join(self.folder, filename), 'r') as f:
                    notes[filename] = f.read()
        return notes

    @staticmethod
    def get_embeddings(texts):
        # Replace with your OpenAI API key
        #openai.api_key = "your_api_key"

        # Filter out empty strings
        texts = [text for text in texts if text.strip()]

        if not texts:
            return np.array([])

        response = openai.Embedding.create(model="text-embedding-ada-002", input=texts)
        embeddings = response['data']
        
        return np.array([np.array(emb["embedding"]) for emb in embeddings])

    def save_embedding_to_redis(self, embedding, filename):
        r = redis.Redis()
        key = f"embedding:{filename}"
        response = r.set(key, embedding.tobytes())
        print(f"{filename} Embedding Redise eklendi.")

    def load_embeddings_from_redis(self):
        r = redis.Redis()
        keys = r.keys("embedding:*")
        note_dates = [key.decode("utf-8").split(":")[1] for key in keys]
        embeddings = []
        for key in keys:
            embedding = np.frombuffer(r.get(key), dtype=np.float64)
            embeddings.append(embedding)
        return note_dates, np.array(embeddings)

    def update_embedding(self, filename):
        if filename in self.notes:
            content = self.notes[filename]
            embedding = self.get_embeddings([content])[0]
            self.save_embedding_to_redis(embedding, filename)
        else:
            print(f"{filename} dosyası bulunamadı.")

    def find_closest(self, query_embedding, note_embeddings):
        return note_embeddings.dot(query_embedding).argmax()

    def update_all_embeddings(self):
        for filename, content in self.notes.items():
            if content.strip():
                embedding = self.get_embeddings([content])[0]
                self.save_embedding_to_redis(embedding, filename)
            else:
                print(f"Doküman boş {filename}. Atlandı.")
    
    def chat_gpt(self, document, question):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sen doküman asistanısın. Dokümanı oku ve soruları cevapla. Sadece dokümanla ilgili soruları cevapla."},
                {"role": "user", "content": document},
                {"role": "assistant", "content": "Ben bir doküman asistanıyım. Yukarıdaki dokümanı okuyup ve sorularınızı cevaplayacağım. Sadece dokümanla ilgili sorularınıza cevap verebilirim, başka sorulara kesinlikle dokümanda yok diye cevap veririm."},
                {"role": "user", "content": question},
            ],
        )
        answer = response.choices[0].message['content']
        return answer

    def run(self, args):
        if args.dosya:
            if args.dosya.lower() == "hepsi":
                self.update_all_embeddings()
            else:
                self.update_embedding(args.dosya)
        else:
            note_dates, note_embeddings = self.load_embeddings_from_redis()

            while True:
                text = input("Soru: ")
                if text.lower() == "bitir":
                    break

                query_embedding = self.get_embeddings([text])[0]
                index = self.find_closest(query_embedding, note_embeddings)
                print(f"En yakın not: {note_dates[index]}")

                #print(self.notes[note_dates[index]])
                
                # Get the answer from the document using ChatGPT API
                document = self.notes[note_dates[index]]
                answer = self.chat_gpt(document, text)
                print(f"Cevap: {answer}")



def parse_arguments():
    parser = argparse.ArgumentParser(description="Notlarını bul")
    parser.add_argument("--dosya", type=str, help="Verisetine yeni bir not eklemek için dosya adını girin.")
    return parser.parse_args()


def main():
    folder = "notlar"
    note_finder = NoteFinder(folder)
    args = parse_arguments()
    note_finder.run(args)


if __name__ == "__main__":
    main()