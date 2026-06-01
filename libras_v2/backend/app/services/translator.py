"""
Serviço de tradução: Texto em português → Sinais de Libras
Lógica: tenta encontrar sinal próprio → se não achar, soletra (datilologia)
"""
import unicodedata
from app.models.schemas import TranslatedToken, TokenType
from app.data.alphabet import LIBRAS_ALPHABET
from app.data.words import LIBRAS_WORDS


def _normalize(text: str) -> str:
    """Remove acentos e converte para minúsculo para comparação"""
    nfkd = unicodedata.normalize('NFKD', text)
    without_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.lower().strip()


def _find_word(text: str):
    """Busca uma palavra/expressão no dicionário de sinais"""
    normalized = _normalize(text)
    for word in LIBRAS_WORDS:
        if _normalize(word.word) == normalized:
            return word
    return None


def _fingerspell(text: str) -> list[dict]:
    """Converte texto em letras do alfabeto (datilologia)"""
    letters = []
    for char in text.upper():
        if char in LIBRAS_ALPHABET:
            sign = LIBRAS_ALPHABET[char]
            letters.append(sign.model_dump())
    return letters


def translate_phrase(phrase: str) -> list[TranslatedToken]:
    """
    Traduz uma frase inteira para Libras.
    
    Algoritmo:
    1. Separa a frase em palavras
    2. Tenta match de expressões compostas (3 palavras, depois 2, depois 1)
    3. Se encontrou sinal próprio → usa o sinal
    4. Se não encontrou → soletra letra por letra (datilologia)
    
    Exemplo: "bom dia Vinicius obrigado"
    → [SINAL(bom dia)] + [SOLETRAR(V-I-N-I-C-I-U-S)] + [SINAL(obrigado)]
    """
    words = phrase.strip().split()
    result: list[TranslatedToken] = []
    
    i = 0
    while i < len(words):
        matched = False
        
        # Tenta match de expressões compostas (do maior para o menor)
        for length in range(3, 0, -1):
            if i + length > len(words):
                continue
            
            candidate = ' '.join(words[i:i + length])
            found = _find_word(candidate)
            
            if found:
                result.append(TranslatedToken(
                    original=candidate,
                    type=TokenType.WORD,
                    signs=[found.model_dump()]
                ))
                i += length
                matched = True
                break
        
        # Se não achou sinal, soletra
        if not matched:
            letters = _fingerspell(words[i])
            if letters:
                result.append(TranslatedToken(
                    original=words[i],
                    type=TokenType.FINGERSPELL,
                    signs=letters
                ))
            i += 1
    
    return result