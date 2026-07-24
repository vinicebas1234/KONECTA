"""LSAE — Libras Semantic Augmentation Engine.

Motor de geração/augmentation de dados sintéticos para treinar reconhecimento
de Libras com melhor generalização entre sinalizantes. Ver PLANO_GENERALIZACAO.md
na raiz do projeto para a arquitetura completa e a ordem de implementação.

Cada pilar é implementado como funções Python puras, testáveis isoladamente,
recebendo os mesmos arrays (X, y, meta) que já saem de
GerenciadorDados.carregar_estaticos()/carregar_dinamicos() em libras_recognizer.py.
Nenhum módulo aqui depende de Tkinter/UI.
"""
