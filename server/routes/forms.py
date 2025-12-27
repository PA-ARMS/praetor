"""
Forms API routes - Legal form generation
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Optional, List
from pathlib import Path
import json
from datetime import datetime

from server.services.ollama_service import ollama_service
from server.services.rag_service import rag_service
from server.services.guardrails_service import guardrails_service
from server.config import settings


router = APIRouter()


class FormData(BaseModel):
    form_type: str
    court: str
    case_data: Dict
    template_fields: Optional[Dict] = None


class FormGenerationRequest(BaseModel):
    form_type: str
    court: str
    case_data: Dict
    generate_workflow: bool = True


@router.post("/generate")
async def generate_form(request: FormGenerationRequest):
    """Generate legal form from case data"""
    try:
        # Get workflow/process information if requested
        workflow_info = ""
        if request.generate_workflow:
            workflow_query = f"Court procedures and workflow for {request.form_type} in {request.court}"
            workflow_results = await rag_service.search(workflow_query, n_results=3)
            if workflow_results:
                workflow_info = "\n".join([r['text'] for r in workflow_results])
        
        # Build prompt for form generation
        system_prompt = guardrails_service.build_system_prompt()
        system_prompt += "\n\nYou are generating a legal form. Fill in all required fields based on the provided case data."
        
        form_prompt = f"""
Generate a {request.form_type} form for {request.court} court.

Case Data:
{json.dumps(request.case_data, indent=2)}

Workflow Information:
{workflow_info if workflow_info else "No specific workflow information found."}

Instructions:
1. Fill in all form fields based on the case data
2. Follow the court's specific formatting requirements
3. Include all required information
4. Use proper legal terminology
5. Ensure all dates and names are correctly formatted

Generate the completed form:
"""
        
        # Generate form content
        form_content = await ollama_service.generate(
            prompt=form_prompt,
            system_prompt=system_prompt
        )
        
        return {
            "form_type": request.form_type,
            "court": request.court,
            "content": form_content,
            "workflow_info": workflow_info,
            "generated_at": datetime.now().isoformat(),
            "verification_required": True
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating form: {str(e)}")


@router.post("/workflow")
async def get_workflow(form_type: str, court: str):
    """Get workflow/process information for a form type"""
    try:
        query = f"Court procedures, deadlines, and workflow requirements for {form_type} in {court} court, Virginia"
        results = await rag_service.search(query, n_results=5)
        
        workflow_info = []
        for result in results:
            workflow_info.append({
                "source": result['metadata'].get('source', 'Unknown'),
                "information": result['text']
            })
        
        return {
            "form_type": form_type,
            "court": court,
            "workflow": workflow_info
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving workflow: {str(e)}")


@router.get("/templates")
async def list_templates():
    """List available form templates"""
    templates_dir = Path(settings.TEMPLATES_DIR)
    templates = []
    
    if templates_dir.exists():
        for template_file in templates_dir.glob("*.docx"):
            templates.append({
                "name": template_file.stem,
                "type": "docx",
                "path": str(template_file)
            })
    
    return {"templates": templates}

