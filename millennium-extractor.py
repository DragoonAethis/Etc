"""
Skrypt do eksportu historii zwykłego konta Millennium do CSV

Ostatnio sprawdzony: 2026-07-20 (Python 3.14, Pandas 2.3.3)

Wymaga Pythona 3 i Pandas (pip install pandas)

Jak używać:
1. Na stronie Millennium otwórz historię konta
2. Kliknij Wyszukiwanie zaawansowane
3. Otwórz devtoolsy w przeglądarce (F12) -> Sieć/Network
   (To powinno zacząć zapisywanie requestów do Millennium)
4. Ustaw na stronie filtry transakcji do eksportu (szczególnie daty)
5. Zacznij klikać Dalej aby przelecieć się przez wszystkie strony.
   W konsoli: document.getElementById("nextButton").click()
   (Nie rób tego pętlą, czasem trzeba coś kliknąć/potwierdzić)
6. Gdy przeklikasz się przez wszystkie transakcje które chcesz
   wyciągnąć, p-klik -> zapisz wszystko jako HAR.
7. Odpal ten skrypt: python millextract.py responses.har

Transakcje są zapisywane do transactions.csv.
"""

import sys
import json
from pprint import pprint

import pandas as pd


allowed_urls = [
    "https://online.bankmillennium.pl/osobiste2/Accounts/CurrentAccountDetails/TransactionsHistorySearchAjax",
    "https://online.bankmillennium.pl/osobiste2/Accounts/CurrentAccountDetails/TransactionsHistoryAjax",
    "https://online.bankmillennium.pl/osobiste2/Accounts/CurrentAccountDetails/TransactionsHistoryPaginationAjax",
]

allowed_mime = "application/json; charset=utf-8"

found_detail_codes = {}


def flatten_tx(tx):
    if 'HistoryDetail' in tx:
        for detail in tx['HistoryDetail']:
            tx[detail['Label']] = detail['Value']

            if detail['Label'] not in found_detail_codes:
                found_detail_codes[detail['Label']] = set()

            found_detail_codes[detail['Label']].add(detail['FieldCode'])

        del tx['HistoryDetail']

    for flatten_key in ['AdditionalInformation', 'AugmentData']:
        if flatten_key in tx and type(tx[flatten_key]) == dict:
            for k, v in tx[flatten_key].items():
                tx[k] = v

            del tx[flatten_key]

    return tx


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        har = json.load(f)

    flat_tx = []
    for entry in har['log']['entries']:
        if entry['request']['url'] not in allowed_urls:
            continue

        if entry['response']['content']['mimeType'] != allowed_mime:
            print(f"BAD MIME TYPE FOR RESPONSE: {json.dumps(entry)}")

        response = json.loads(entry['response']['content']['text'])
        flat_tx += [flatten_tx(tx) for tx in response['Transactions']]

    pd.DataFrame(flat_tx).to_csv('transactions.csv', header=True, index=False)

    print("Done - found field detail codes:")
    pprint(found_detail_codes)
