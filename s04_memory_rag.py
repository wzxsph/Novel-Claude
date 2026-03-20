import re
import chromadb
from chromadb.utils import embedding_functions
from zhipuai import ZhipuAI
from utils.config import MEMORY_DIR, ANTHROPIC_API_KEY, register_background_task
from utils.llm_client import extract_entities, client as llm_client, MODEL_ID

class ZhipuEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self):
        self.client = ZhipuAI(api_key=ANTHROPIC_API_KEY)
        
    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings = []
        for text in input:
            res = self.client.embeddings.create(model="embedding-3", input=text)
            embeddings.append(res.data[0].embedding)
        return embeddings

chroma_client = chromadb.PersistentClient(path=MEMORY_DIR)
emb_fn = ZhipuEmbeddingFunction()
collection = chroma_client.get_or_create_collection(name="novel_memory", embedding_function=emb_fn)

def condense_state(entity: str, context_chunks: list[str]) -> str:
    """Summarizes the latest state of an entity based on retrieved chunks."""
    prompt = f"你是一个情报总结官。根据以下小说文本片段，极简总结实体【{entity}】的最新状态（例如：伤势、法宝受损情况、对其余人物的恨意等）。不要编造，如果文本没提就回复“状态正常”。\n\n" + "\n\n---\n\n".join(context_chunks)
    messages = [{"role": "user", "content": prompt}]
    res = llm_client.chat.completions.create(model=MODEL_ID, messages=messages, temperature=0.1)
    return res.choices[0].message.content.strip()

def pre_generation_hook(beat_data: dict) -> str:
    """
    【拦截器 - 前置注入】：在 Subagent 启动前为其准备最新的一批状态弹药
    """
    entities = extract_entities(beat_data.get('plot_summary', ''))
    if not entities:
        return ""
        
    try:
        from rich.console import Console
        Console().print(f"[bold cyan]  [Memory Bus][/bold cyan] 嗅探到关键实体: {entities}，正在检索最新状态...")
    except:
        print(f"  [Memory Bus] 嗅探到关键实体: {entities}，正在检索最新状态...")

    recent_memories = []
    
    for entity in entities:
        results = collection.query(
            query_texts=[entity],
            n_results=5
        )
        
        if results and results['documents'] and len(results['documents'][0]) > 0:
            docs = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            # Combine doc and metadata to sort by chapter_id
            combined = list(zip(docs, metadatas))
            combined.sort(key=lambda x: x[1].get('chapter_id', 0), reverse=True)
            
            # Take top 3 recent chunks
            recent_chunks = [c[0] for c in combined[:3]]
            condensed = condense_state(entity, recent_chunks)
            if condensed and "状态正常" not in condensed:
                recent_memories.append(f"- {entity}: {condensed}")
                
    if not recent_memories:
        return ""
        
    xml_memory = "<recent_memory>\n[实体最新状态同步]\n"
    xml_memory += "\n".join(recent_memories)
    xml_memory += "\n</recent_memory>\n\n"
    
    return xml_memory

def chunk_text(text: str) -> list[str]:
    """
    User architecture feedback: 
    优先按自然段（\n\n）或场景分割符（***）进行 Chunking，确保存入向量库的每一个片段（Document）都具有相对完整的语义。
    """
    # Split by *** or \n\n
    raw_chunks = re.split(r'\*\*\*|\n\s*\n', text)
    chunks = []
    
    current_chunk = ""
    for rc in raw_chunks:
        rc = rc.strip()
        if not rc: continue
        # If the segment is too small, accumulate
        if len(current_chunk) + len(rc) < 200:
            current_chunk += "\n" + rc if current_chunk else rc
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = rc
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

def _background_update_task(chapter_id: int, final_content: str):
    try:
        from rich.console import Console
        Console().print(f"[dim]  [Background Task] 正在将第 {chapter_id} 章内容向量化并入库...[/dim]")
    except:
        print(f"  [Background Task] 正在将第 {chapter_id} 章内容向量化并入库...")
        
    chunks = chunk_text(final_content)
    
    ids = []
    documents = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        chunk_entities = extract_entities(chunk)
        if chunk_entities:
            involved = ",".join(chunk_entities)
            documents.append(chunk)
            ids.append(f"ch_{chapter_id}_chunk_{i}")
            metadatas.append({
                "chapter_id": chapter_id,
                "involved_entities": involved
            })
            
    if documents:
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

def post_generation_hook(chapter_id: int, final_content: str):
    """
    【拦截器 - 后置刷新】：章节落盘后，异步更新世界记忆
    """
    # 绝不阻塞主线程的推进，使用线程抛出后台任务，并由 config.py 的 Tracker 捕获以备后用
    register_background_task(_background_update_task, chapter_id, final_content)
