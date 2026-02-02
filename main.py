import os
import json
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from itertools import cycle

app = FastAPI(title="Technobolt AI Shopper")

# ==========================================
# GERENCIADOR DE CHAVES (RODÍZIO OTIMIZADO)
# ==========================================
class KeyManager:
    def __init__(self):
        self.keys = []
        # Procura de chaves 1 a 7 nas variáveis de ambiente
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
# MODELOS DE DADOS (PYDANTIC)
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

# NOVOS MODELOS
class ListaRequest(BaseModel):
    itens_lista: List[str] # Lista de planejamento

class ConferenciaRequest(BaseModel):
    lista_planejada: List[str]
    itens_carrinho: List[str]

# ==========================================
# FUNÇÕES AUXILIARES DE IA
# ==========================================

def get_gemini_model():
    """Configura e retorna o modelo com a próxima chave do rodízio."""
    current_key = key_manager.get_next_key()
    genai.configure(api_key=current_key)
    # Usando o modelo flash conforme solicitado para rapidez e custo
    return genai.GenerativeModel('models/gemini-flash-latest')

def clean_json_response(text: str):
    """Limpa formatações markdown que a IA possa enviar."""
    return text.replace("```json", "").replace("```", "").strip()

# ==========================================
# ROTAS DA API
# ==========================================

@app.get("/")
def read_root():
    return {"status": "Technobolt Brain Online", "keys_active": len(key_manager.keys)}

# --- ROTA 1: ANÁLISE DE PREÇOS (DURANTE A COMPRA) ---
@app.post("/analisar_compras")
async def analisar_compras(request: AnaliseRequest):
    if not request.produtos:
        return {"analise": []}

    try:
        model = get_gemini_model()
        lista_json = json.dumps([p.dict() for p in request.produtos], ensure_ascii=False)
        
        prompt = f"""
        Atue como especialista em economia doméstica.
        Analise a lista: {lista_json}. Orçamento: R$ {request.orcamento_total:.2f}.
        
        Regras:
        1. Alerta 'red' para preços unitários absurdamente caros para o Brasil.
        2. Alerta 'orange' para supérfluos se o gasto total estiver próximo do orçamento.
        3. Alerta 'yellow' para quantidades suspeitas (ex: 10kg de sal).
        
        Retorne APENAS JSON: [{{ "id": "...", "alerta": "none/yellow/orange/red", "feedback": "texto curto" }}]
        """
        
        response = model.generate_content(prompt)
        analise_json = json.loads(clean_json_response(response.text))
        return {"analise": analise_json}

    except Exception as e:
        print(f"Erro Analise: {e}")
        return {"analise": []}

# --- ROTA 2: SUGESTÃO DE RECEITA (PÓS COMPRA) ---
@app.post("/sugerir_receita")
async def sugerir_receita(request: ReceitaRequest):
    if not request.ingredientes:
        return {"titulo": "Ops", "receita_texto": "Adicione itens ao carrinho para eu sugerir algo!"}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.ingredientes)
        
        prompt = f"""
        Atue como uma cozinheira amiga. O usuário quer fazer: "{request.tipo_refeicao}".
        Ingredientes disponíveis: {lista_str}.
        
        Gere UMA receita.
        Diretrizes de Estilo (IMPORTANTE):
        - NÃO use símbolos markdown como negrito (**), itálico (*) ou cabeçalhos (###).
        - Use apenas texto simples e quebras de linha.
        - Fale diretamente com a pessoa ("Você vai precisar...").
        - Se faltar um ingrediente essencial (ex: ovo, leite) que não está na lista, AVISE no texto.
        
        Retorne APENAS JSON:
        {{
            "titulo": "Nome do Prato",
            "receita_texto": "Texto corrido da receita, ingredientes e modo de preparo..."
        }}
        """
        
        response = model.generate_content(prompt)
        return json.loads(clean_json_response(response.text))

    except Exception as e:
        print(f"Erro Receita: {e}")
        return {"titulo": "Erro no Chef", "receita_texto": "Tente novamente em instantes."}

# --- ROTA 3: SUGERIR COMPLEMENTOS (PLANEJAMENTO) ---
@app.post("/sugerir_complementos_lista")
async def sugerir_complementos(request: ListaRequest):
    if not request.itens_lista:
        return {"sugestoes": []}

    try:
        model = get_gemini_model()
        lista_str = ", ".join(request.itens_lista)
        
        prompt = f"""
        Analise esta lista de compras planejada: {lista_str}.
        Identifique itens complementares essenciais que parecem estar faltando.
        Exemplo: Se tem 'Macarrão' mas não 'Molho', sugira Molho.
        Exemplo: Se tem 'Café' mas não 'Açúcar/Adoçante', sugira.
        Exemplo: Se tem 'Shampoo' mas não 'Condicionador', sugira.
        
        Retorne APENAS JSON (Lista de objetos):
        [
            {{
                "item_base": "Item da lista que gerou a dica",
                "sugestao": "O que comprar",
                "motivo": "Explicação curta"
            }}
        ]
        Limite a no máximo 3 sugestões mais críticas. Se a lista estiver boa, retorne [].
        """
        
        response = model.generate_content(prompt)
        return {"sugestoes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Complementos: {e}")
        return {"sugestoes": []}

# --- ROTA 4: CONFERÊNCIA DE CARRINHO (CHECKLIST) ---
@app.post("/conferir_carrinho")
async def conferir_carrinho(request: ConferenciaRequest):
    # Se não planejou nada, não tem o que conferir
    if not request.lista_planejada:
        return {"faltantes": []}

    try:
        model = get_gemini_model()
        
        prompt = f"""
        Atue como um conferente inteligente.
        Lista Planejada: {', '.join(request.lista_planejada)}
        Carrinho (Já pego): {', '.join(request.itens_carrinho)}
        
        Tarefa: Retorne quais itens da 'Lista Planejada' NÃO estão no 'Carrinho'.
        Use inteligência semântica (Ex: Se planejou 'Refrigerante' e pegou 'Coca-Cola', considere como pego/ok).
        
        Retorne APENAS JSON (Lista de Strings):
        ["Item Faltante 1", "Item Faltante 2"]
        Se pegou tudo, retorne [].
        """
        
        response = model.generate_content(prompt)
        return {"faltantes": json.loads(clean_json_response(response.text))}

    except Exception as e:
        print(f"Erro Conferencia: {e}")
        return {"faltantes": []}
