"""
Simplified Financial Agent using CrewAI Tools
This replaces the complex manual routing with tool-based approach
"""

from crewai import Agent, Task, Crew
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from app.tools.financial_tools import add_expense_tool, add_income_tool, generate_report_tool, list_organizations_tool, create_organization_tool, set_tool_context
from app.tools.report_tools import set_report_tool_context


class FinancialAgent:
    """Simplified financial agent using proper CrewAI Tools architecture"""
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.has_openai = get_openai_config()
        
        if self.has_openai:
            # Set global context for tools
            set_tool_context(db, user_id)
            set_report_tool_context(db)
            
            # Initialize tools
            self.tools = [
                add_expense_tool,
                add_income_tool,
                generate_report_tool,
                list_organizations_tool,
                create_organization_tool
            ]
            
            # Create agent with tools
            self.agent = Agent(
                role="Asistente Financiero Personal",
                goal="Ayudar al usuario a gestionar sus finanzas de manera natural y eficiente usando las herramientas disponibles.",
                backstory="""Eres un asistente financiero experto que ayuda a usuarios latinos a:

• Registrar gastos e ingresos de forma natural
• Generar reportes y resúmenes financieros  
• Gestionar organizaciones familiares y empresariales
• Entender patrones de gasto y dar consejos

PRINCIPIOS CORE:
1. USA LAS HERRAMIENTAS - Siempre identifica qué herramienta usar
2. SÉ NATURAL - Entiende el español coloquial costarricense
3. SÉ PRECISO - Extrae cantidades y descripciones exactas
4. SÉ INTELIGENTE - Infiere organizaciones cuando sea obvio

EJEMPLOS DE USO DE HERRAMIENTAS:
• "Gasto 500 almuerzo" → usar add_expense con amount=500, description="almuerzo"
• "Gasté 40000 gasolina familia" → usar add_expense con amount=40000, description="gasolina", organization_context="familia"
• "ingreso 60000 personal" → usar add_income con amount=60000, description="ingreso general", organization_context="personal"
• "salario 150000" → usar add_income con amount=150000, description="salario"
• "cobré 25000 freelance" → usar add_income con amount=25000, description="freelance"
• "Resumen personal" → usar generate_report con period="este mes", organization="personal"
• "En qué familias estoy" → usar list_organizations
• "Lista de organizaciones" → usar list_organizations
• "En cuales organizaciones estoy" → usar list_organizations
• "Mis organizaciones" → usar list_organizations
• "Crear familia Mi Hogar" → usar create_organization con organization_name="Mi Hogar"

IMPORTANTE: SIEMPRE usa las herramientas para ejecutar acciones. No intentes manejar lógica compleja manualmente.""",
                verbose=True,
                allow_delegation=False,
                tools=self.tools
            )
        else:
            self.agent = None
    
    def process_message(self, message: str) -> Dict[str, Any]:
        """Process user message using tools-based approach"""
        
        if not self.has_openai or not self.agent:
            return self._fallback_processing(message)
        
        try:
            # Create task for the agent
            task = Task(
                description=f"""
                El usuario envió este mensaje: "{message}"
                
                Analiza el mensaje y usa la herramienta apropiada:
                
                1. Si es un GASTO/EXPENSE → usa add_expense (gasto, gasté, pagué, compré, etc.)
                2. Si es un INGRESO/INCOME → usa add_income (ingreso, salario, cobré, recibí, gané, etc.)
                3. Si es un reporte/resumen → usa generate_report  
                4. Si es consulta de organizaciones → usa list_organizations (en qué familias, mis organizaciones, lista organizaciones)
                5. Si es crear organización → usa create_organization
                
                INSTRUCCIONES ESPECÍFICAS:
                • Extrae cantidades exactas (ej: "500", "40000")
                • Identifica descripciones claras (ej: "almuerzo", "gasolina")
                • Detecta contexto organizacional si se menciona (ej: "familia", "personal", "empresa")
                • Para reportes, identifica período (ej: "hoy", "esta semana") y organización (ej: "personal", "familia")
                
                EJEMPLOS:
                • "Gasto 500 almuerzo" → add_expense(amount=500, description="almuerzo")
                • "ingreso 60000 personal" → add_income(amount=60000, description="ingreso general", organization_context="personal")
                • "salario 150000" → add_income(amount=150000, description="salario")
                • "Resumen familia" → generate_report(period="este mes", organization="familia")
                • "En qué familias estoy" → list_organizations()
                • "Lista de organizaciones" → list_organizations()
                • "Crear familia Nueva" → create_organization(organization_name="Nueva")
                
                Responde directamente con el resultado de la herramienta.
                """,
                agent=self.agent,
                expected_output="Respuesta procesada usando las herramientas apropiadas"
            )
            
            # Execute with CrewAI
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                memory=True,  # Enable memory for context
                verbose=True
            )
            
            result = crew.kickoff()
            
            return {
                "success": True,
                "message": str(result).strip(),
                "action": "tool_processed"
            }
            
        except Exception as e:
            print(f"Error in FinancialAgent: {e}")
            return self._fallback_processing(message)
    
    def _fallback_processing(self, message: str) -> Dict[str, Any]:
        """Fallback processing when OpenAI is not available"""
        
        message_lower = message.lower().strip()
        
        # Simple regex fallback
        import re
        
        # Check for expense patterns
        expense_patterns = [
            r'(gasto|gasté|compré|pago|pagué)\s*(\d+)',
            r'(\d+)\s*(almuerzo|comida|gasolina|café)'
        ]
        
        for pattern in expense_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    # Extract amount
                    amount = float(re.search(r'\d+', message).group())
                    description = message_lower.replace(str(int(amount)), '').strip()
                    description = re.sub(r'(gasto|gasté|compré|pago|pagué)', '', description).strip()
                    
                    if not description:
                        description = "gasto general"
                    
                    # Use tool directly
                    result = add_expense_tool(amount=amount, description=description)
                    
                    return {
                        "success": True,
                        "message": result,
                        "action": "expense_added"
                    }
                except:
                    pass
        
        # Check for report patterns
        if any(word in message_lower for word in ["resumen", "reporte", "balance", "gastos"]):
            try:
                result = generate_report_tool(period="este mes", organization=None)
                
                return {
                    "success": True,
                    "message": result,
                    "action": "report_generated"
                }
            except:
                pass
        
        # Check for organization patterns
        if any(word in message_lower for word in ["organizaciones", "familias", "lista", "qué familias", "en cuales", "mis organizaciones"]):
            try:
                result = list_organizations_tool()
                
                return {
                    "success": True,
                    "message": result,
                    "action": "organizations_listed"
                }
            except:
                pass
        
        # Default response
        return {
            "success": False,
            "message": "🤔 No entendí tu mensaje.\n\n💡 **Puedes probar:**\n\n💸 'Gasté ₡5000 en almuerzo'\n📊 'Resumen de gastos'\n🏷️ 'En qué familias estoy'\n❓ 'Ayuda'",
            "action": "unknown"
        }