import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from itertools import combinations
from collections import defaultdict
from sklearn.cluster import KMeans
import telebot
from datetime import datetime, timedelta

# Konfiguracja
TELEGRAM_TOKEN = '7969643661:AAFvcj9F48lh9a5A_Z6tI_ctnb9Su736mM0'  # Z @BotFather
TELEGRAM_CHAT_ID = 8034812917   # Z @userinfobot
TIMEZONE = 'Europe/Warsaw'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

class LottoAnalyzer:
    def __init__(self):
        self.games = {
            'Mini Lotto': {
                'url': 'https://www.lotto.pl/mini-lotto/wyniki-i-wygrane',
                'cols': ['L1', 'L2', 'L3', 'L4', 'L5'],
                'n_clusters': 3
            },
            'Lotto': {
                'url': 'https://www.lotto.pl/lotto/wyniki-i-wygrane',
                'cols': ['L1', 'L2', 'L3', 'L4', 'L5', 'L6'],
                'n_clusters': 4
            },
            'Multi Multi': {
                'url': 'https://www.lotto.pl/multi-multi/wyniki-i-wygrane',
                'cols': [f'L{i}' for i in range(1, 21)],
                'n_clusters': 5
            },
            'EuroJackpot': {
                'url': 'https://www.lotto.pl/eurojackpot/wyniki-i-wygrane',
                'cols': ['L1', 'L2', 'L3', 'L4', 'L5'],
                'extra_cols': ['E1', 'E2'],
                'n_clusters': 3
            }
        }

    def scrape_data(self, game_name):
        try:
            game = self.games[game_name]
            response = requests.get(game['url'])
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for row in soup.select('.wynik'):
                date_str = row.select_one('.date').text.strip()
                date = datetime.strptime(date_str, '%d.%m.%Y')
                numbers = [int(num.text) for num in row.select('.number')]
                
                if game_name == 'EuroJackpot':
                    main_numbers = numbers[:5]
                    extra_numbers = numbers[5:7]
                    results.append([date] + main_numbers + extra_numbers)
                else:
                    results.append([date] + numbers)
            
            columns = ['Data'] + game['cols']
            if game_name == 'EuroJackpot':
                columns += game['extra_cols']
                
            return pd.DataFrame(results, columns=columns)
        except Exception as e:
            print(f"Błąd pobierania {game_name}: {e}")
            return pd.DataFrame()

    def analyze_frequency(self, df, cols):
        return df[cols].stack().value_counts().sort_values(ascending=False)

    def analyze_pairs(self, df, cols):
        pairs = defaultdict(int)
        for _, row in df.iterrows():
            for pair in combinations(sorted(row[cols]), 2):
                pairs[pair] += 1
        return dict(sorted(pairs.items(), key=lambda x: -x[1]))

    def analyze_cold_numbers(self, df, cols):
        last_seen = {}
        return_days = {}
        
        for _, row in df.sort_values('Data').iterrows():
            for num in row[cols]:
                if num in last_seen:
                    return_days[num] = (row['Data'] - last_seen[num]).days
                last_seen[num] = row['Data']
        
        return dict(sorted(return_days.items(), key=lambda x: -x[1]))

    def generate_variants(self, df, game_name):
        game = self.games[game_name]
        cols = game['cols']
        
        freq = self.analyze_frequency(df, cols)
        pairs = self.analyze_pairs(df, cols)
        cold = self.analyze_cold_numbers(df, cols)
        
        # Wariant 1: Najczęstsze liczby
        v1 = freq.head(5).index.tolist()
        
        # Wariant 2: Najlepsze pary
        top_pairs = list(pairs.items())[:10]
        pair_counts = defaultdict(int)
        for pair, count in top_pairs:
            for num in pair:
                pair_counts[num] += count
        v2 = sorted(pair_counts, key=lambda x: -pair_counts[x])[:5]
        
        # Wariant 3: Klastrowanie
        kmeans = KMeans(n_clusters=game['n_clusters'])
        df['Cluster'] = kmeans.fit_predict(df[cols])
        cluster_means = df.groupby('Cluster')[cols].mean()
        v3 = cluster_means.stack().sort_values(ascending=False).head(5).index.get_level_values(1).tolist()
        
        # Wariant 4: Gorące + zimne
        hot = freq.head(3).index.tolist()
        cold_list = list(cold.keys())[:2]
        v4 = hot + cold_list
        
        # Wariant 5: Losowe ważone
        weights = freq / freq.sum()
        v5 = np.random.choice(weights.index, size=5, p=weights, replace=False).tolist()
        
        variants = [
            ("Najczęstsze", v1),
            ("Najlepsze pary", v2),
            ("Klastrowe", v3),
            ("Gorące+zimne", v4),
            ("Losowe ważone", v5)
        ]
        
        # Dodatkowe liczby dla EuroJackpot
        if game_name == 'EuroJackpot':
            extra_freq = self.analyze_frequency(df, game['extra_cols'])
            extra_nums = extra_freq.head(2).index.tolist()
            variants = [(name, nums + extra_nums) if i < 3 else (name, nums) for i, (name, nums) in enumerate(variants)]
        
        return variants

def send_report():
    analyzer = LottoAnalyzer()
    message = "🏆 KOMPLETNA ANALIZA LOTTO 🏆\n\n"
    
    for game_name in analyzer.games:
        df = analyzer.scrape_data(game_name)
        if df.empty:
            message += f"⚠️ Brak danych dla {game_name}\n\n"
            continue
            
        variants = analyzer.generate_variants(df, game_name)
        freq = analyzer.analyze_frequency(df, analyzer.games[game_name]['cols'])
        cold = analyzer.analyze_cold_numbers(df, analyzer.games[game_name]['cols'])
        
        message += f"🎯 {game_name.upper()} 🎯\n"
        for name, nums in variants:
            nums_str = ', '.join(map(str, sorted(nums))) if isinstance(nums[0], int) else ', '.join(nums)
            message += f"🔹 {name}: {nums_str}\n"
        
        message += f"\n🔥 TOP 3: {', '.join(map(str, freq.head(3).index.tolist()))}\n"
        message += f"❄️ NAJZIMNIEJSZE: {', '.join(f'{k}({v}d)' for k,v in list(cold.items())[:3])}\n\n"
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        print("Raport wysłany pomyślnie")
    except Exception as e:
        print(f"Błąd wysyłania: {e}")

if __name__ == "__main__":
    send_report()