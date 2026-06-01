<<<<<<< HEAD
# 🤟 KONECTA — Reconhecimento de Libras com Visão Computacional

Projeto de Trabalho de Conclusão de Curso (TCC) focado no desenvolvimento de uma solução de **reconhecimento de sinais em Libras (Língua Brasileira de Sinais)** por meio de **Visão Computacional**, **Inteligência Artificial** e **Processamento de Imagens**.

O sistema tem como propósito capturar movimentos das mãos em tempo real, identificar sinais e convertê-los em texto, promovendo **acessibilidade**, **inclusão digital** e apoio à comunicação entre pessoas surdas e ouvintes.

---

## 📌 Sobre o Projeto

O **KONECTA** é um projeto acadêmico desenvolvido como TCC, com foco na aplicação prática de tecnologias modernas para resolver um problema real de acessibilidade.

A proposta central do projeto é construir uma ferramenta capaz de:

- Capturar imagens da câmera em tempo real;
- Detectar mãos e pontos de referência (landmarks);
- Processar sinais de Libras;
- Classificar letras, números ou gestos treinados;
- Converter o sinal reconhecido em texto;
- Permitir a expansão futura para frases, voz e interface web.

Além do aspecto técnico, o projeto também busca demonstrar como a tecnologia pode ser aplicada para gerar **impacto social positivo**.

---

## 🎯 Objetivos

### Objetivo Geral

Desenvolver um sistema computacional capaz de reconhecer sinais em Libras por meio de visão computacional e inteligência artificial, traduzindo os gestos para texto de forma automatizada.

### Objetivos Específicos

- Implementar captura de vídeo em tempo real;
- Detectar mãos com precisão por meio de bibliotecas especializadas;
- Registrar e organizar dados para treinamento;
- Criar uma base de dados de sinais;
- Treinar e testar modelos de reconhecimento;
- Exibir os sinais reconhecidos em uma interface acessível;
- Contribuir para soluções de acessibilidade baseadas em tecnologia.

---

## 🧠 Tecnologias Utilizadas

O projeto utiliza ferramentas e bibliotecas amplamente adotadas em aplicações de visão computacional e desenvolvimento em Python:

- **Python** — linguagem principal do projeto;
- **OpenCV** — captura e processamento de imagens;
- **MediaPipe** — detecção de mãos e pontos de referência;
- **Tkinter** — interface gráfica local;
- **NumPy** — manipulação de dados numéricos;
- **Scikit-learn / TensorFlow / outras bibliotecas de IA** — treinamento e reconhecimento (conforme a versão do projeto);
- **Git e GitHub** — versionamento e documentação do projeto.

---

## 🏗️ Estrutura do Repositório

```text
KONECTA/
│
├── OCR/                           # Módulo principal do sistema
│   ├── dados_libras/              # Base de dados local (ignorada no Git)
│   ├── .vscode/                   # Configurações locais da IDE (ignorada)
│   ├── requirements.txt           # Dependências do projeto
│   ├── importar_dataset_libras.py # Script principal/utilitário
│   ├── importar_dataset_libras_CORRIGIDO.py
│   ├── importar_dataset_libras_CORRIGIDO (1).py
│   ├── importacao.log             # Logs (ignorados)
│   └── ...
│
├── Datasets/                      # Conjunto de dados geral (ignorado)
├── libras_v2/                     # Versões alternativas / experimentos
├── vlibra/                        # Integrações e testes complementares
├── .venv/                         # Ambiente virtual (ignorado)
├── .gitignore                     # Regras de exclusão para versionamento
└── README.md                      # Este arquivo
```

> **Observação:** alguns diretórios variam conforme a evolução do projeto, testes locais e versões de scripts utilizadas durante o desenvolvimento do TCC.

---

## ⚙️ Requisitos

Antes de executar o projeto, recomenda-se ter instalado:

- **Python 3.10+** (ou versão compatível com as bibliotecas utilizadas);
- **pip** atualizado;
- Webcam funcional;
- Sistema operacional Windows, Linux ou macOS;
- Git (opcional, para versionamento e contribuição).

Para atualizar o `pip`:

```bash
python -m pip install --upgrade pip
```

---

## 🚀 Como Executar o Projeto

### 1. Clonar o repositório

```bash
git clone https://github.com/vinicebas1234/KONECTA.git
cd KONECTA
```

### 2. Criar o ambiente virtual

```bash
python -m venv .venv
```

### 3. Ativar o ambiente virtual

**No Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**No Windows (CMD):**

```cmd
.venv\Scripts\activate.bat
```

**No Git Bash:**

```bash
source .venv/Scripts/activate
```

**No Linux/macOS:**

```bash
source .venv/bin/activate
```

### 4. Instalar as dependências

```bash
pip install -r OCR/requirements.txt
```

### 5. Executar o sistema

```bash
python OCR/importar_dataset_libras.py
```

> Caso o arquivo principal da sua versão atual seja outro, substitua o nome do script pelo correspondente.

---

## 🔍 Funcionalidades do Sistema

Entre as funcionalidades já implementadas ou previstas no escopo do projeto, destacam-se:

- 📷 Captura de vídeo em tempo real por webcam;
- 🖐 Detecção de mãos e landmarks;
- 🔠 Reconhecimento de sinais, letras e números;
- 🧾 Conversão do sinal reconhecido em texto;
- 🗂 Coleta e organização de datasets personalizados;
- 🧠 Base para treinamento de modelos de classificação;
- 🖥 Interface local para operação e testes;
- ♿ Aplicação voltada para acessibilidade e inclusão.

---

## 🧪 Metodologia de Desenvolvimento

O projeto foi desenvolvido em etapas, seguindo uma abordagem incremental:

1. **Estudo do problema e definição da proposta**;
2. **Pesquisa sobre Libras, IA e visão computacional**;
3. **Escolha das tecnologias e bibliotecas**;
4. **Criação da estrutura do projeto em Python**;
5. **Implementação da captura e detecção de mãos**;
6. **Coleta e organização da base de dados**;
7. **Testes de reconhecimento e ajustes no modelo**;
8. **Documentação técnica e acadêmica para o TCC**.

Essa metodologia permite evolução contínua, testes frequentes e refinamento progressivo da solução.

---

## 📚 Aplicação Acadêmica

Este repositório faz parte de um **Trabalho de Conclusão de Curso (TCC)** na área de tecnologia, com ênfase em:

- Acessibilidade digital;
- Inclusão social;
- Inteligência Artificial aplicada;
- Visão computacional;
- Reconhecimento de padrões;
- Desenvolvimento de soluções tecnológicas com impacto social.

O projeto também pode servir como base para estudos futuros, prototipagem de soluções reais e evolução para ferramentas educacionais ou assistivas.

---

## ♿ Impacto Social

A proposta do KONECTA vai além da implementação técnica. O sistema busca contribuir para:

- Melhorar a comunicação entre pessoas surdas e ouvintes;
- Incentivar o uso da tecnologia como ferramenta de inclusão;
- Demonstrar aplicações práticas da IA em problemas reais;
- Ampliar o acesso à informação por meio da automação da tradução de sinais.

Projetos dessa natureza são importantes para aproximar inovação tecnológica e responsabilidade social.

---

## 📂 Arquivos Ignorados no Git

Alguns arquivos e diretórios não são versionados por conterem dados locais, temporários ou de grande volume.

Exemplos:

```gitignore
.venv/
Datasets/
OCR/dados_libras/
OCR/.vscode/
*.log
__pycache__/
*.pyc
```

Esses itens são mantidos fora do repositório para evitar envio de arquivos desnecessários, dados sensíveis, logs e ambientes locais.

---

## 🛠️ Possíveis Melhorias Futuras

O projeto pode ser expandido com diversas melhorias, como:

- Reconhecimento de palavras e frases completas;
- Síntese de voz a partir do texto reconhecido;
- Interface web ou aplicação mobile;
- Treinamento com modelos mais robustos de Deep Learning;
- Maior diversidade de sinais e contextos de uso;
- Armazenamento em banco de dados;
- Painel de acompanhamento de desempenho do modelo;
- Integração com APIs e serviços de acessibilidade.

---

## 👨‍💻 Autor

**Vinicius Rosa Santos**  
Assistente de Infraestrutura  
Estudante e desenvolvedor do projeto **KONECTA**  

- GitHub: [vinicebas1234](https://github.com/vinicebas1234)

---

## 📄 Licença

Este projeto possui finalidade **acadêmica e educacional**.

Caso deseje publicar uma licença específica, recomenda-se adicionar um arquivo `LICENSE` ao repositório.

Exemplos de licenças comuns:

- MIT License
- Apache 2.0
- GPL v3

---

## 🤝 Contribuições

Como se trata de um projeto acadêmico, contribuições podem ser analisadas conforme a necessidade do desenvolvimento.

Caso deseje colaborar:

1. Faça um fork do repositório;
2. Crie uma branch para sua modificação;
3. Realize as alterações necessárias;
4. Envie um pull request.

---

## 📬 Contato

Se desejar conhecer mais sobre o projeto ou trocar ideias sobre tecnologia, acessibilidade e IA, utilize o GitHub do autor para contato e acompanhamento das atualizações.

---

## ⭐ Considerações Finais

O **KONECTA** representa a união entre conhecimento acadêmico, desenvolvimento prático e impacto social.

Mais do que um sistema de reconhecimento de Libras, este projeto demonstra como a tecnologia pode ser usada para criar soluções inclusivas, acessíveis e relevantes para a sociedade.
=======
# KONECTA
Software para tradução simultânea de Libras x Português
>>>>>>> 07168eed2c6602e0165ac6aca7c63dbc781f683d
