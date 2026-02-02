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
        self.keys = []
        for i in range(1, 8): 
            key = os.environ.get(f"GEMINI_CHAVE_{i}")
            if key:
                self.keys.append(key)
        
        if not self.keys:
            print("⚠️ AVISO: Nenhuma chave API encontrada (GEMINI_CHAVE_1 ... 7).")
            self.keys = ["dummy_key"] 
            
        self.key_cycle = cycle(self.keys)

    def get_next_key(self):
        return next(self.key_cycle)

key_manager = KeyManager()

# ==========================================
# MODELOS DE DADOS
# ==========================================

class Produto(BaseModel):
    id: str
    nome: str
    preco_unitario: float
    quantidade: float 

class AnaliseRequest(BaseModel):
    produtos: List[Produto]
    orcamento_total: float

class ReceitaRequest(BaseModel):
    ingredientes: List[str]
    tipo_refeicao: str

class ListaRequest(BaseModel):
    itens_lista: List[str]

class ConferenciaRequest(BaseModel):
    lista_planejada: List[str]
    itens_carrinho: List[str]

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def get_gemini_model():
    """Configura e retorna o modelo com a próxima chave."""
    current_key = key_manager.get_next_key()
    genai.configure(api_key=current_key)
    return genai.GenerativeModel('models/gemini-flash-latest')

def clean_json_response(text: str):
    """Garante que a resposta seja JSON puro sem markdown."""
    return text.replace("```json", "").replace("```", "").strip()

# ==========================================
# ROTAS DA API
# ==========================================

@app.get("/")
def read_root():
    return {"status": "Technobolt Brain Online", "keys_active": len(key_manager.keys)}

# --- ROTA 1: ANÁLISE DE PREÇOS (AMIGA ECONOMISTA) ---
@app.post("/analisar_compras")
async def analisar_compras(request: AnaliseRequest):
    if not request.produtos:
        return {"analise": []}

    try:
        model = get_gemini_model()
        lista_json = json.dumps([p.dict() for p in request.produtos], ensure_ascii=False)
        
        prompt = f"""
        Atue como uma amiga economista que quer ajudar a dona de casa a poupar.
        Analise a lista: {lista_json}. Orçamento Total: R$ {request.orcamento_total:.2f}.
        
        Regras de Análise:
        1. Preços Abusivos: Compare mentalmente com a média brasileira. Se for muito caro, alerta 'red'.
        2. Supérfluos: Se o orçamento estiver apertado, marque itens não essenciais com alerta 'orange'.
        3. Quantidades: Alerte 'yellow' para quantidades exageradas.
        
        Regras de Texto (Feedback):
        - Linguagem natural e carinhosa, mas direta.
        - Dê uma dica prática (ex: "Troque por marca tal", "Leve pacote maior").
        - PROIBIDO usar símbolos como asteriscos (**), hashtags (##) ou markdown. Use apenas texto puro.
        - Não use saudações. Vá direto ao conselho.
        
        Retorne APENAS JSON: [{{ "id": "...", "alerta": "none/yellow/orange/red", "feedback": "Conselho prático e amigável aqui." }}]
        """
        
        response = model.generate_content(prompt)
        analise_json = json.loads(clean_json_response(response.text))
        return {"analise": analise_json}

    except Exception as e:
        print(f"Erro Analise: {e}")
        return {"analise": []}

# --- ROTA 2: SUGESTÃO DE RECEITA (CHEF AMIGA) ---
@app.post("/sugerir_receita")
async def sugerir_receita(request: ReceitaRequest):
    if not request.ingredientes:
        return {"titulo": "Ops", "receita_texto": "Adicione itens ao carrinho para eu criar uma receita."}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.ingredientes)
        
        prompt = f"""
        Você é uma cozinheira experiente e criativa.
        Crie uma receita incrível de "{request.tipo_refeicao}" usando o máximo destes ingredientes: {lista_str}.
        
        ESTRUTURA DA RESPOSTA (Obrigatório seguir):
        1. Comece direto com o nome do prato (sem "Aqui está").
        2. Liste os ingredientes de forma simples.
        3. Explique o modo de preparo como se estivesse ensinando uma amiga (passo a passo fluido).
        4. No final, adicione uma "Dica de Ouro" ou "Segredo do Chef" para o prato ficar especial.
        
        REGRAS VISUAIS:
        - PROIBIDO usar Markdown (nada de negrito **, itálico *, títulos ##).
        - Use apenas quebras de linha e letras maiúsculas para destacar TÍTULOS DE SEÇÕES se precisar.
        - Texto limpo e fácil de ler no celular.
        
        Retorne APENAS JSON:
        {{
            "titulo": "Nome Criativo do Prato",
            "receita_texto": "Texto completo da receita (ingredientes, preparo e dica extra)..."
        }}
        """
        
        response = model.generate_content(prompt)
        return json.loads(clean_json_response(response.text))

    except Exception as e:
        print(f"Erro Receita: {e}")
        return {"titulo": "Erro na Cozinha", "receita_texto": "Tente novamente em alguns segundos."}

# --- ROTA 3: SUGERIR COMPLEMENTOS (MEMÓRIA AUXILIAR) ---
@app.post("/sugerir_complementos_lista")
async def sugerir_complementos(request: ListaRequest):
    if not request.itens_lista:
        return {"sugestoes": []}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.itens_lista)
        
        prompt = f"""
        Analise a lista de compras: {lista_str}.
        Pense como quem cuida da casa: O que a pessoa esqueceu para completar as refeições ou limpeza?
        
        Regras:
        1. Identifique conexões lógicas (ex: Café sem Filtro? Macarrão sem Queijo? Sabão sem Amaciante?).
        2. Sugira apenas o essencial que parece faltar.
        
        Retorno JSON (Texto limpo, sem markdown):
        [ {{ "item_base": "Item da lista", "sugestao": "O que falta", "motivo": "Explicação breve e útil (ex: Para não faltar no café)" }} ]
        Máximo 3 sugestões principais.
        """
        
        response = model.generate_content(prompt)
        return {"sugestoes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Complementos: {e}")
        return {"sugestoes": []}

# --- ROTA 4: CONFERÊNCIA DE CARRINHO (CHECKLIST INTELIGENTE) ---
@app.post("/conferir_carrinho")
async def conferir_carrinho(request: ConferenciaRequest):
    if not request.lista_planejada:
        return {"faltantes": []}

    try:
        model = get_gemini_model()
        
        prompt = f"""
        Atue como um conferente atento.
        Lista Planejada: {', '.join(request.lista_planejada)}
        Carrinho: {', '.join(request.itens_carrinho)}
        
        Tarefa: Retorne quais itens da Lista Planejada ainda NÃO foram pegos.
        Seja inteligente: Se a lista diz "Refrigerante" e no carrinho tem "Guaraná", considere pego.
        
        Retorne APENAS uma lista JSON simples de Strings com os nomes dos itens faltantes.
        Exemplo: ["Feijão", "Detergente"]
        """
        
        response = model.generate_content(prompt)
        return {"faltantes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Conferencia: {e}")
        return {"faltantes": []}
