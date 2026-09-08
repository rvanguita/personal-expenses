# Categorize as transações usando:

{category}

# Retorne JSON com:
Estabelecimento, Categoria, Motivo.

# Regras:
- Só utilize as categorias enviadas no início deste documento. Se não encontrar, use "not_found".
- Créditos/pagamentos de fatura: Categoria = "not_found" e Motivo = "not_found".
- O Motivo deve generalizar o Estabelecimento em no máximo duas palavras.
- Antes de criar um novo Motivo, verifique os Motivos já existentes.
- Se um Motivo existente representar o mesmo tipo de estabelecimento/serviço, reutilize exatamente o Motivo existente.
- Não crie variações, sinônimos ou plurais de Motivos já existentes.
- Só crie um novo Motivo quando nenhum Motivo existente for semanticamente equivalente.
- Motivos devem ser genéricos e reutilizáveis entre diferentes estabelecimentos.
- Não invente informações.