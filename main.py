import os
import json
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from itertools import cycle

app = FastAPI(title="Technobolt AI Shopper")

# --- GERENCIADOR DE CHAVES (RODÍZIO) ---
class KeyManager:
    def __init__(self):
        # Carrega as chaves das variáveis de ambiente
        self.keys = []
        for i in range(1, 8): # Procura de 1 a 7
            key = os.environ.get(f"GEMINI_API_KEY_{i}")
            if key:
                self.keys.append(key)
        
        if not self.keys:
            print("⚠️ AVISO: Nenhuma chave API encontrada nas variáveis de ambiente.")
            self.keys = ["dummy_key"] # Evita crash na inicialização, mas falhará na requisição
            
        self.key_cycle = cycle(self.keys) # Cria um iterador infinito (loop)

    def get_next_key(self):
        return next(self.key_cycle)

key_manager = KeyManager()

# --- MODELOS DE DADOS ---
class Produto(BaseModel):
    id: str
    nome: str
    preco_unitario: float
    quantidade: int

class AnaliseRequest(BaseModel):
    produtos: List[Produto]
    orcamento_total: float

# --- CONFIGURAÇÃO DO PROMPT ---
def gerar_prompt(produtos, orcamento):
    lista_json = json.dumps([p.dict() for p in produtos], ensure_ascii=False)
    
    return f"""
    Atue como um assistente de economia doméstica especialista.
    Analise a seguinte lista de compras e o orçamento total de R$ {orcamento:.2f}.
    
    Lista: {lista_json}
    
    Regras de Análise:
    1. Identifique produtos com preço unitário suspeito (muito caro para a média de mercado brasileiro).
    2. Identifique produtos supérfluos se o orçamento estiver apertado (gasto total > 80% do orçamento).
    3. Identifique erros de quantidade (ex: 100 caixas de leite pode ser erro de digitação).
    
    Saída OBRIGATÓRIA: Retorne APENAS um JSON puro (sem markdown ```json) com uma lista de objetos.
    Cada objeto deve ter exatamente este formato:
    {{
        "id": "id_do_produto_original",
        "alerta": "nivel_de_alerta", 
        "feedback": "mensagem curta e direta"
    }}
    
    Níveis de alerta:
    - "none": Produto ok, preço justo, essencial.
    - "yellow": Atenção leve (ex: pouco essencial ou preço levemente alto).
    - "orange": Cuidado (ex: item supérfluo com orçamento apertado).
    - "red": Crítico (ex: preço absurdo, erro de digitação provável, estoura o orçamento sozinho).
    """

# --- ROTAS ---
@app.get("/")
def read_root():
    return {"status": "Technobolt AI Brain Online", "keys_loaded": len(key_manager.keys)}

@app.post("/analisar_compras")
async def analisar_compras(request: AnaliseRequest):
    if not request.produtos:
        return {"analise": []}

    try:
        # 1. Pega a próxima chave do rodízio
        current_key = key_manager.get_next_key()
        
        # 2. Configura a API
        genai.configure(api_key=current_key)
        
        # Usamos o flash por ser rápido e barato/gratuito
        model = genai.GenerativeModel('models/gemini-flash-latest')
        
        # 3. Gera o conteúdo
        prompt = gerar_prompt(request.produtos, request.orcamento_total)
        response = model.generate_content(prompt)
        
        # 4. Tratamento da resposta (Limpeza do Markdown)
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        analise_json = json.loads(texto_limpo)
        
        return {"analise": analise_json}

    except Exception as e:
        print(f"Erro na IA: {e}")
        # Fallback simples em caso de erro da API para o app não travar
        return {
            "analise": [],
            "error": "Serviço de IA indisponível no momento, tente novamente."
        }
