from crewai import Agent, Task, Crew
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.core.llm_config import get_openai_config
from app.services.user_service import UserService
from app.services.family_service import FamilyService
import json
import re

class ContextAgent:
    """
    Intelligent agent that helps users choose the right context (personal, family, company) 
    for their transactions in a natural, conversational way.
    """
    
    def __init__(self):
        try:
            # Setup OpenAI environment
            self.has_openai = get_openai_config()
            
            if self.has_openai:
                self.agent = Agent(
                    role="Smart Financial Context Assistant",
                    goal="Help users naturally choose the right context (personal, family, or work) for their financial transactions based on their available organizations and the nature of the expense.",
                    backstory="""Eres un asistente financiero inteligente que ayuda a usuarios a organizar sus gastos. 
                    Entiendes que las personas pueden tener múltiples contextos financieros:
                    - Gastos personales (solo para ellos)
                    - Gastos familiares (compartidos con familia/roommates)  
                    - Gastos de trabajo (empresa/departamento)
                    
                    Tu trabajo es preguntar de forma natural y amigable dónde va cada gasto cuando no está claro.
                    Siempre hablas en español de forma conversacional, como un amigo que ayuda con las finanzas.
                    Eres inteligente para inferir contexto basado en la descripción del gasto.""",
                    verbose=True,
                    allow_delegation=False
                )
            else:
                self.agent = None
                
        except Exception as e:
            print(f"Warning: Failed to initialize ContextAgent: {e}")
            self.has_openai = False
            self.agent = None
    
    def analyze_transaction_context(self, transaction_description: str, amount: float, user_contexts: List[Dict]) -> Dict[str, Any]:
        """
        Analyzes a transaction and determines if context clarification is needed.
        
        Args:
            transaction_description: The parsed transaction description
            amount: Transaction amount
            user_contexts: List of available contexts for the user
            
        Returns:
            Dict with analysis results and suggested actions
        """
        
        # If user only has personal context, no need to ask
        if len(user_contexts) <= 1:
            return {
                "needs_clarification": False,
                "suggested_context": "personal",
                "confidence": "high",
                "reason": "only_personal_context"
            }
        
        # Use AI to analyze if context is clear from description
        if self.has_openai and self.agent:
            return self._ai_analyze_context(transaction_description, amount, user_contexts)
        else:
            return self._fallback_analyze_context(transaction_description, user_contexts)
    
    def _ai_analyze_context(self, description: str, amount: float, contexts: List[Dict]) -> Dict[str, Any]:
        """Use AI to analyze transaction context."""
        try:
            contexts_text = "\n".join([
                f"- {ctx['name']} ({ctx['type']})" for ctx in contexts
            ])
            
            task = Task(
                description=f"""
                Analiza esta transacción y determina si es claro a qué contexto pertenece:
                
                Transacción: "{description}" por {amount}
                
                Contextos disponibles del usuario:
                {contexts_text}
                
                Analiza si la descripción indica claramente el contexto:
                
                CLARAMENTE PERSONAL: gastos muy personales (ropa personal, medicina personal, entretenimiento solo, etc.)
                CLARAMENTE FAMILIAR: gastos del hogar (supermercado, servicios de casa, limpieza, etc.)
                CLARAMENTE TRABAJO: gastos empresariales (almuerzo de negocios, materiales de oficina, viajes de trabajo, etc.)
                NO CLARO: podría ser cualquier contexto (almuerzo, gasolina, etc.)
                
                Responde en JSON:
                {{
                    "is_context_clear": true/false,
                    "suggested_context": "personal/family/work/unclear",
                    "confidence": "high/medium/low",
                    "reasoning": "explicación breve"
                }}
                """,
                agent=self.agent,
                expected_output="JSON con análisis de contexto"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            try:
                analysis = json.loads(result)
                
                return {
                    "needs_clarification": not analysis.get("is_context_clear", False),
                    "suggested_context": analysis.get("suggested_context", "unclear"),
                    "confidence": analysis.get("confidence", "low"),
                    "reasoning": analysis.get("reasoning", "")
                }
                
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return self._fallback_analyze_context(description, contexts)
                
        except Exception as e:
            print(f"Error in AI context analysis: {e}")
            return self._fallback_analyze_context(description, contexts)
    
    def _fallback_analyze_context(self, description: str, contexts: List[Dict]) -> Dict[str, Any]:
        """Fallback context analysis using simple rules."""
        desc_lower = description.lower()
        
        # Clear personal indicators
        personal_keywords = ["personal", "mi ", "mio", "medicina", "doctor", "ropa", "entretenimiento"]
        if any(keyword in desc_lower for keyword in personal_keywords):
            return {
                "needs_clarification": False,
                "suggested_context": "personal",
                "confidence": "high",
                "reason": "personal_keywords"
            }
        
        # Clear family/household indicators  
        family_keywords = ["casa", "hogar", "supermercado", "mercado", "limpieza", "servicios", "internet", "luz", "agua"]
        if any(keyword in desc_lower for keyword in family_keywords):
            family_context = next((ctx for ctx in contexts if ctx['type'] == 'family'), None)
            if family_context:
                return {
                    "needs_clarification": False,
                    "suggested_context": "family",
                    "confidence": "medium",
                    "reason": "family_keywords"
                }
        
        # Clear work indicators
        work_keywords = ["trabajo", "oficina", "cliente", "reunion", "viaje de trabajo", "materiales oficina"]
        if any(keyword in desc_lower for keyword in work_keywords):
            work_context = next((ctx for ctx in contexts if ctx['type'] in ['company', 'department', 'team']), None)
            if work_context:
                return {
                    "needs_clarification": False,
                    "suggested_context": "work",
                    "confidence": "medium",
                    "reason": "work_keywords"
                }
        
        # If multiple contexts available and not clear, ask user
        return {
            "needs_clarification": True,
            "suggested_context": "unclear",
            "confidence": "low",
            "reason": "ambiguous_description"
        }
    
    def generate_context_question(self, transaction_description: str, amount: float, currency: str, user_contexts: List[Dict]) -> str:
        """
        Generates a natural question asking user to choose context.
        """
        
        if self.has_openai and self.agent:
            return self._ai_generate_context_question(transaction_description, amount, currency, user_contexts)
        else:
            return self._fallback_generate_context_question(transaction_description, amount, currency, user_contexts)
    
    def _ai_generate_context_question(self, description: str, amount: float, currency: str, contexts: List[Dict]) -> str:
        """Use AI to generate natural context question."""
        try:
            contexts_text = ""
            for i, ctx in enumerate(contexts, 1):
                icon = self._get_context_icon(ctx['type'])
                contexts_text += f"{icon} {ctx['name']} ({self._get_context_description(ctx)})\n"
            
            task = Task(
                description=f"""
                Genera una pregunta natural y amigable para que el usuario elija dónde va esta transacción:
                
                Transacción: "{description}" por {currency}{amount:,.0f}
                
                Contextos disponibles:
                {contexts_text}
                
                La pregunta debe ser:
                - Natural y conversacional en español
                - Amigable y no robótica  
                - Incluir emojis apropiados
                - Explicar brevemente qué significa cada opción
                - Terminar con instrucciones simples de cómo responder
                
                Ejemplo de tono: "¡Perfecto! Registré tu gasto de..."
                """,
                agent=self.agent,
                expected_output="Pregunta natural y amigable"
            )
            
            crew = Crew(agents=[self.agent], tasks=[task])
            result = str(crew.kickoff()).strip()
            
            return result
            
        except Exception as e:
            print(f"Error generating AI context question: {e}")
            return self._fallback_generate_context_question(description, amount, currency, contexts)
    
    def _fallback_generate_context_question(self, description: str, amount: float, currency: str, contexts: List[Dict]) -> str:
        """Fallback context question generation."""
        
        question = f"¡Perfecto! Registré tu gasto de {currency}{amount:,.0f} en {description} 💰\n\n¿A dónde va este gasto?\n"
        
        for ctx in contexts:
            icon = self._get_context_icon(ctx['type'])
            desc = self._get_context_description(ctx)
            question += f"{icon} {ctx['name']} ({desc})\n"
        
        question += "\nSolo responde con el nombre del contexto o 'personal', 'familia', 'trabajo' 😊"
        
        return question
    
    def _get_context_icon(self, context_type: str) -> str:
        """Get emoji icon for context type."""
        icons = {
            "personal": "🏠",
            "family": "👨‍👩‍👧‍👦", 
            "team": "👥",
            "department": "🏢",
            "company": "🏢"
        }
        return icons.get(context_type, "📋")
    
    def _get_context_description(self, context: Dict) -> str:
        """Get friendly description for context."""
        context_type = context['type']
        
        descriptions = {
            "personal": "solo tuyo",
            "family": "compartido con familia/roommates",
            "team": "gasto de equipo",
            "department": "gasto de departamento", 
            "company": "gasto de empresa"
        }
        
        return descriptions.get(context_type, "gasto compartido")
    
    def parse_context_response(self, user_response: str, available_contexts: List[Dict]) -> Optional[Dict]:
        """
        Parses user's response to context question and returns selected context.
        """
        
        response_lower = user_response.lower().strip()
        
        # Direct matches
        if response_lower in ["personal", "personal", "mio", "yo"]:
            return {"type": "personal", "id": None, "name": "Personal"}
        
        if response_lower in ["familia", "family", "casa", "hogar", "roommates"]:
            family_ctx = next((ctx for ctx in available_contexts if ctx['type'] == 'family'), None)
            return family_ctx
        
        if response_lower in ["trabajo", "work", "empresa", "oficina"]:
            work_ctx = next((ctx for ctx in available_contexts if ctx['type'] in ['company', 'department', 'team']), None)
            return work_ctx
        
        # Try to match by name
        for ctx in available_contexts:
            if ctx['name'].lower() in response_lower or response_lower in ctx['name'].lower():
                return ctx
        
        return None
    
    def get_user_contexts(self, db: Session, user_id: str) -> List[Dict]:
        """
        Get all available contexts for a user (personal + organizations).
        """
        contexts = [
            {"type": "personal", "id": None, "name": "Personal"}
        ]
        
        # Get user's organizations
        try:
            from app.models.organization import Organization, OrganizationMember
            
            user_organizations = db.query(Organization).join(OrganizationMember).filter(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            ).all()
            
            for org in user_organizations:
                contexts.append({
                    "type": org.type.value,  # family, team, department, company
                    "id": str(org.id),
                    "name": org.name
                })
        except Exception as e:
            print(f"Error getting user organizations: {e}")
        
        return contexts