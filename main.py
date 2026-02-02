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
    # Mantendo exatamente o motor solicitado
    return genai.GenerativeModel('models/gemini-flash-latest')

def clean_json_response(text: str):
    """Limpa formatações markdown."""
    return text.replace("```json", "").replace("```", "").strip()

# ==========================================
# ROTAS DA API
# ==========================================

@app.get("/")
def read_root():
    return {"status": "Technobolt Brain Online", "keys_active": len(key_manager.keys)}

# --- ROTA 1: ANÁLISE DE PREÇOS ---
@app.post("/analisar_compras")
async def analisar_compras(request: AnaliseRequest):
    if not request.produtos:
        return {"analise": []}

    try:
        model = get_gemini_model()
        lista_json = json.dumps([p.dict() for p in request.produtos], ensure_ascii=False)
        
        # Prompt Ajustado: Sem conversinha, direto ao ponto
        prompt = f"""
        Analise a lista: {lista_json}. Orçamento: R$ {request.orcamento_total:.2f}.
        
        Regras de Saída:
        1. Alerta 'red' para preços unitários absurdos (muito acima da média Brasil).
        2. Alerta 'orange' para supérfluos se o gasto total estiver quase estourando.
        3. Alerta 'yellow' para quantidades suspeitas (ex: 10kg de sal).
        4. O 'feedback' DEVE ser uma frase curta e direta. NÃO use "Olá", "Atenção", "Cuidado". Vá direto ao fato.
        
        Retorne APENAS JSON: [{{ "id": "...", "alerta": "none/yellow/orange/red", "feedback": "texto curto" }}]
        """
        
        response = model.generate_content(prompt)
        analise_json = json.loads(clean_json_response(response.text))
        return {"analise": analise_json}

    except Exception as e:
        print(f"Erro Analise: {e}")
        return {"analise": []}

# --- ROTA 2: SUGESTÃO DE RECEITA ---
@app.post("/sugerir_receita")
async def sugerir_receita(request: ReceitaRequest):
    if not request.ingredientes:
        return {"titulo": "Ops", "receita_texto": "Adicione itens ao carrinho."}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.ingredientes)
        
        # Prompt Ajustado: Proibido saudações
        prompt = f"""
        Você é um chef de cozinha direto e prático.
        Crie uma receita de "{request.tipo_refeicao}" usando: {lista_str}.
        
        REGRAS RIGÍDAS DE TEXTO:
        1. NÃO use saudações (ex: "Olá", "Claro", "Aqui está").
        2. NÃO repita o título da receita no campo 'receita_texto'.
        3. NÃO use Markdown pesado (sem ### ou **). Use apenas quebras de linha.
        4. Comece o texto IMEDIATAMENTE com a lista de ingredientes ou modo de preparo.
        5. Se faltar algo essencial (ovo, leite), avise no meio do texto de forma natural.
        
        Retorne APENAS JSON:
        {{
            "titulo": "Nome Criativo do Prato",
            "receita_texto": "Ingredientes:... Modo de Preparo:..."
        }}
        """
        
        response = model.generate_content(prompt)
        return json.loads(clean_json_response(response.text))

    except Exception as e:
        print(f"Erro Receita: {e}")
        return {"titulo": "Erro", "receita_texto": "Tente novamente."}

# --- ROTA 3: SUGERIR COMPLEMENTOS ---
@app.post("/sugerir_complementos_lista")
async def sugerir_complementos(request: ListaRequest):
    if not request.itens_lista:
        return {"sugestoes": []}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.itens_lista)
        
        prompt = f"""
        Analise a lista planejada: {lista_str}.
        Identifique o que falta para completar combinações óbvias (ex: Macarrão sem Molho).
        
        Regras:
        1. Seja cirúrgico. Apenas o que é essencial.
        2. 'motivo' deve ser curto (ex: "Para acompanhar o macarrão").
        
        Retorne APENAS JSON:
        [ {{ "item_base": "Item da lista", "sugestao": "O que falta", "motivo": "Explicação curta" }} ]
        Máximo 3 sugestões.
        """
        
        response = model.generate_content(prompt)
        return {"sugestoes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Complementos: {e}")
        return {"sugestoes": []}

# --- ROTA 4: CONFERÊNCIA DE CARRINHO ---
@app.post("/conferir_carrinho")
async def conferir_carrinho(request: ConferenciaRequest):
    if not request.lista_planejada:
        return {"faltantes": []}

    try:
        model = get_gemini_model()
        
        prompt = f"""
        Lista Planejada: {', '.join(request.lista_planejada)}
        Carrinho: {', '.join(request.itens_carrinho)}
        
        Retorne APENAS uma lista JSON com as Strings dos itens que estão na Planejada mas NÃO estão no Carrinho.
        Use inteligência semântica.
        Retorno: ["Item A", "Item B"]
        """
        
        response = model.generate_content(prompt)
        return {"faltantes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Conferencia: {e}")
        return {"faltantes": []}
