from app.models.schemas import LibrasWord

# Dicionário de palavras/expressões com sinal próprio
LIBRAS_WORDS: list[LibrasWord] = [
    # 👋 Saudações
    LibrasWord(id="ola", word="olá", category="saudacoes",
               hint="Acene com a mão aberta.", image_url="/static/signs/words/ola.gif"),
    LibrasWord(id="bom-dia", word="bom dia", category="saudacoes",
               hint="Sinal de BOM + sinal de DIA (sol nascendo).", image_url="/static/signs/words/bom-dia.gif"),
    LibrasWord(id="boa-tarde", word="boa tarde", category="saudacoes",
               hint="Sinal de BOA + sinal de TARDE (sol descendo).", image_url="/static/signs/words/boa-tarde.gif"),
    LibrasWord(id="boa-noite", word="boa noite", category="saudacoes",
               hint="Sinal de BOA + sinal de NOITE (lua).", image_url="/static/signs/words/boa-noite.gif"),
    LibrasWord(id="obrigado", word="obrigado", category="saudacoes",
               hint="Mão aberta no queixo, move para frente.", image_url="/static/signs/words/obrigado.gif"),
    LibrasWord(id="por-favor", word="por favor", category="saudacoes",
               hint="Mão aberta no peito, movimento circular.", image_url="/static/signs/words/por-favor.gif"),
    LibrasWord(id="desculpa", word="desculpa", category="saudacoes",
               hint="Mão em A no peito, movimento circular.", image_url="/static/signs/words/desculpa.gif"),
    LibrasWord(id="tudo-bem", word="tudo bem", category="saudacoes",
               hint="Sinal de TUDO + sinal de BEM (polegar para cima).", image_url="/static/signs/words/tudo-bem.gif"),

    # ❤️ Sentimentos
    LibrasWord(id="feliz", word="feliz", category="sentimentos",
               hint="Mãos abertas subindo do peito.", image_url="/static/signs/words/feliz.gif"),
    LibrasWord(id="triste", word="triste", category="sentimentos",
               hint="Mão descendo na frente do rosto.", image_url="/static/signs/words/triste.gif"),
    LibrasWord(id="amor", word="amor", category="sentimentos",
               hint="Braços cruzados no peito.", image_url="/static/signs/words/amor.gif"),
    LibrasWord(id="raiva", word="raiva", category="sentimentos",
               hint="Mãos em garra subindo do peito.", image_url="/static/signs/words/raiva.gif"),

    # 🏫 Escola / Educação
    LibrasWord(id="escola", word="escola", category="escola",
               hint="Palmas batendo duas vezes.", image_url="/static/signs/words/escola.gif"),
    LibrasWord(id="professor", word="professor", category="escola",
               hint="Indicadores apontando para frente, alternando.", image_url="/static/signs/words/professor.gif"),
    LibrasWord(id="estudar", word="estudar", category="escola",
               hint="Mão aberta batendo na palma (como livro).", image_url="/static/signs/words/estudar.gif"),
    LibrasWord(id="aluno", word="aluno", category="escola",
               hint="Mão em C na testa, descendo.", image_url="/static/signs/words/aluno.gif"),

    # 🔢 Perguntas
    LibrasWord(id="o-que", word="o que", category="perguntas",
               hint="Indicador balançando lateralmente.", image_url="/static/signs/words/o-que.gif"),
    LibrasWord(id="como", word="como", category="perguntas",
               hint="Mãos abertas virando para cima.", image_url="/static/signs/words/como.gif"),
    LibrasWord(id="quando", word="quando", category="perguntas",
               hint="Indicador fazendo círculo no ar.", image_url="/static/signs/words/quando.gif"),
    LibrasWord(id="onde", word="onde", category="perguntas",
               hint="Indicador apontando para baixo, balançando.", image_url="/static/signs/words/onde.gif"),

    # 🕐 Tempo
    LibrasWord(id="hoje", word="hoje", category="tempo",
               hint="Mãos abertas descendo na frente do corpo.", image_url="/static/signs/words/hoje.gif"),
    LibrasWord(id="amanha", word="amanhã", category="tempo",
               hint="Polegar no queixo, movendo para frente.", image_url="/static/signs/words/amanha.gif"),
    LibrasWord(id="ontem", word="ontem", category="tempo",
               hint="Polegar apontando para trás sobre o ombro.", image_url="/static/signs/words/ontem.gif"),

    # 👤 Pronomes
    LibrasWord(id="eu", word="eu", category="pronomes",
               hint="Indicador apontando para si mesmo.", image_url="/static/signs/words/eu.gif"),
    LibrasWord(id="voce", word="você", category="pronomes",
               hint="Indicador apontando para a pessoa.", image_url="/static/signs/words/voce.gif"),
    LibrasWord(id="nos", word="nós", category="pronomes",
               hint="Indicador fazendo círculo incluindo a si.", image_url="/static/signs/words/nos.gif"),
]