import os
import json
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from itertools import cycle

app = FastAPI(title="Technobolt AI Shopper")

# ==========================================
# GERENCIADOR DE CHAVES (RODÍZIO)
# ==========================================
class KeyManager:
    def __init__(self):
        # Carrega as chaves das variáveis de ambiente
        self.keys = []
        for i in range(1, 8): # Procura de GEMINI_API_KEY_1 até GEMINI_API_KEY_7
            key = os.environ.get(f"GEMINI_CHAVE_{i}")
            if key:
                self.keys.append(key)
        
        if not self.keys:
            print("⚠️ AVISO: Nenhuma chave API encontrada nas variáveis de ambiente.")
            self.keys = ["dummy_key"] 
            
        self.key_cycle = cycle(self.keys) # Cria um loop infinito das chaves

    def get_next_key(self):
        return next(self.key_cycle)

key_manager = KeyManager()

# ==========================================
# MODELOS DE DADOS
# ==========================================

# Modelo para Análise de Preço/Orçamento
class Produto(BaseModel):
    id: str
    nome: str
    preco_unitario: float
    quantidade: int

class AnaliseRequest(BaseModel):
    produtos: List[Produto]
    orcamento_total: float

# NOVO: Modelo para Pedido de Receita
class ReceitaRequest(BaseModel):
    ingredientes: List[str] # Apenas os nomes dos produtos
    tipo_refeicao: str      # Ex: "Almoço", "Jantar", "Lanche", "Café da Manhã"

# ==========================================
# PROMPTS
# ==========================================

def gerar_prompt_analise(produtos, orcamento):
    lista_json = json.dumps([p.dict() for p in produtos], ensure_ascii=False)
    
    return f"""
    Atue como um assistente de economia doméstica.
    Analise esta lista de compras e o orçamento de R$ {orcamento:.2f}.
    Lista: {lista_json}
    
    Regras:
    1. Identifique preços suspeitos (muito caros).
    2. Identifique supérfluos se o gasto > 80% do orçamento.
    3. Identifique erros de quantidade.
    
    Saída OBRIGATÓRIA: JSON puro com lista de objetos:
    {{ "id": "...", "alerta": "none/yellow/orange/red", "feedback": "msg curta" }}
    """

def gerar_prompt_receita(ingredientes, tipo_refeicao):
    lista_str = ", ".join(ingredientes)
    
    return f"""
    Atue como uma cozinheira experiente e amiga (persona humana).
    O usuário quer fazer um "{tipo_refeicao}" e comprou estes itens: {lista_str}.
    
    Sua missão:
    1. Crie UMA receita deliciosa usando o máximo possível desses itens.
    2. Pode assumir que o usuário tem o básico em casa (sal, óleo, água, açúcar), mas se a receita precisar de algo específico que NÃO está na lista (ex: ovos, leite, fermento), você DEVE avisar.
    
    Formato da Resposta:
    - Fale como uma pessoa, sem usar formatação de Markdown pesada (sem ###, sem negritos excessivos).
    - Comece com o Nome do Prato.
    - Liste os ingredientes (destacando: "Você vai precisar comprar X se não tiver em casa").
    - Passo a passo numerado e simples.
    
    Saída OBRIGATÓRIA: Um JSON puro com este formato:
    {{
        "titulo": "Nome do Prato",
        "receita_texto": "Texto completo da receita aqui, falando diretamente com o usuário..."
    }}
    """

# ==========================================
# ROTAS DA API
# ==========================================

@app.get("/")
def read_root():
    return {"status": "Technobolt Brain Online", "keys_loaded": len(key_manager.keys)}

# Rota 1: Analisa Preços e Orçamento
@app.post("/analisar_compras")
async def analisar_compras(request: AnaliseRequest):
    if not request.produtos:
        return {"analise": []}

    try:
        current_key = key_manager.get_next_key()
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('models/gemini-flash-latest')
        
        prompt = gerar_prompt_analise(request.produtos, request.orcamento_total)
        response = model.generate_content(prompt)
        
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        analise_json = json.loads(texto_limpo)
        
        return {"analise": analise_json}

    except Exception as e:
        print(f"Erro Analise: {e}")
        return {"analise": [], "error": str(e)}

# Rota 2: Sugere Receita (NOVA)
@app.post("/sugerir_receita")
async def sugerir_receita(request: ReceitaRequest):
    if not request.ingredientes:
        return {"titulo": "Ops", "receita_texto": "Preciso de ingredientes para sugerir algo!"}

    try:
        current_key = key_manager.get_next_key()
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('models/gemini-flash-latest')
        
        prompt = gerar_prompt_receita(request.ingredientes, request.tipo_refeicao)
        response = model.generate_content(prompt)
        
        # Limpeza para garantir que venha apenas o JSON
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        
        try:
            receita_json = json.loads(texto_limpo)
        except json.JSONDecodeError:
            # Caso a IA falhe em mandar JSON, retornamos o texto cru formatado manualmente
            return {
                "titulo": "Sugestão do Chef",
                "receita_texto": texto_limpo
            }
        
        return receita_json

    except Exception as e:
        print(f"Erro Receita: {e}")
        return {
            "titulo": "Erro no Chef", 
            "receita_texto": "Não consegui criar a receita agora. Tente novamente."
        }
