"""
report.py — SentinelX AI Phase 4 Router
==========================================
FastAPI router that pulls all events and audit logs for a given record_id,
compiles them, and generates a structured print-friendly PDF report.
"""

import io
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import AuditLog, Event

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incident-report", tags=["Incident Reports"])

# ── Colors ────────────────────────────────────────────────────────────────────
PRIMARY_COLOR = colors.HexColor("#1a2234")    # Dark blue/slate
SECONDARY_COLOR = colors.HexColor("#312e81")  # Muted indigo
TEXT_DARK = colors.HexColor("#1e293b")        # Slate 800
TEXT_MUTED = colors.HexColor("#64748b")       # Slate 500
BORDER_COLOR = colors.HexColor("#cbd5e1")     # Slate 300
BG_LIGHT = colors.HexColor("#f8fafc")         # Slate 50

# Alert colors
DANGER_RED = colors.HexColor("#dc2626")       # Red 600
WARNING_AMBER = colors.HexColor("#d97706")    # Amber 600
SUCCESS_GREEN = colors.HexColor("#16a34a")    # Green 600

@router.get("/{record_id}", response_class=StreamingResponse)
def get_incident_pdf_report(record_id: str, db: Session = Depends(get_db)):
    """
    Generate and stream a professional PDF incident report for the specified record_id.
    """
    # ── 1. Fetch data from DB ─────────────────────────────────────────────────
    events = db.query(Event).filter(Event.record_id == record_id).all()
    audits = db.query(AuditLog).filter(AuditLog.record_id == record_id).all()

    if not events and not audits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No incident logs found in database for record_id '{record_id}'."
        )

    # ── 2. Extract and format values ──────────────────────────────────────────
    # Sort events by created_at
    events_sorted = sorted(events, key=lambda e: e.created_at)
    
    anomaly_score = None
    is_anomalous = False
    reason_codes: List[str] = []
    
    mitre_techniques = []
    explanation = ""
    predicted_next_stage = ""
    attack_confidence = 0.0
    
    risk_score = 0
    risk_tier = "monitor"
    recommended_actions = []
    approval_required = False
    approval_state = "auto"
    approver = None
    executed_at = None

    for ev in events_sorted:
        payload = ev.payload or {}
        resp = payload.get("response") or payload
        
        if ev.stage == "predict":
            anomaly_score = resp.get("anomaly_score")
            is_anomalous = resp.get("is_anomalous", False)
            reason_codes = resp.get("reason_codes", [])
        elif ev.stage == "investigate":
            mitre_techniques = resp.get("mitre_techniques", [])
            explanation = resp.get("explanation", "")
            predicted_next_stage = resp.get("predicted_next_stage", "")
            attack_confidence = resp.get("attack_confidence", 0.0)

    # Parse containment audits
    if audits:
        # Get the latest audit log entry
        latest_audit = sorted(audits, key=lambda a: a.created_at)[-1]
        risk_score = latest_audit.risk_score or 0
        risk_tier = latest_audit.risk_tier or "monitor"
        approval_required = latest_audit.approval_required or False
        approval_state = latest_audit.approval_state or "auto"
        approver = latest_audit.approver
        executed_at = latest_audit.executed_at
        
        if latest_audit.action:
            recommended_actions = [a.strip() for a in latest_audit.action.split(",") if a.strip()]

    # ── 3. Build ReportLab PDF ────────────────────────────────────────────────
    buffer = io.BytesIO()
    
    # Page template setup
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.white,
        spaceAfter=0,
        alignment=0
    )
    
    h1_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=PRIMARY_COLOR,
        spaceBefore=14,
        spaceAfter=6,
        borderColor=BORDER_COLOR,
        borderWidth=0.5,
        borderPadding=4
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=TEXT_DARK
    )
    
    meta_val_style = ParagraphStyle(
        'MetaValue',
        fontName='Helvetica',
        fontSize=10,
        textColor=TEXT_DARK
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        textColor=TEXT_DARK,
        leading=13
    )

    mono_style = ParagraphStyle(
        'CodeStyle',
        fontName='Courier',
        fontSize=8.5,
        textColor=colors.HexColor("#0f172a"),
        leading=11
    )

    story = []
    
    # ── Document Title Banner ─────────────────────────────────────────────────
    banner_data = [
        [
            Paragraph("SENTINELX AI — INCIDENT REPORT", title_style),
            Paragraph(f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", ParagraphStyle('BannerTime', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=2))
        ]
    ]
    banner_table = Table(banner_data, colWidths=[340, 200])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY_COLOR),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 15))
    
    # ── Executive Summary Meta Panel ──────────────────────────────────────────
    status_text = "MONITORING"
    status_color = SUCCESS_GREEN
    
    if approval_state == "pending":
        status_text = "PENDING MITIGATION"
        status_color = WARNING_AMBER
    elif approval_state == "executed":
        status_text = "CONTAINED & APPROVED"
        status_color = SUCCESS_GREEN
    elif approval_state == "rejected":
        status_text = "MITIGATION REJECTED"
        status_color = DANGER_RED
    elif risk_tier in ("critical", "elevated") and approval_state == "auto":
        status_text = "AUTO-CONTAINED"
        status_color = WARNING_AMBER

    summary_data = [
        [
            Paragraph("Incident Record ID:", meta_label_style),
            Paragraph(f"<b>{record_id}</b>", meta_val_style),
            Paragraph("Threat Risk Tier:", meta_label_style),
            Paragraph(f"<font color='{risk_tier.lower() == 'critical' and '#dc2626' or '#d97706'}'><b>{risk_tier.upper()}</b></font>", meta_val_style)
        ],
        [
            Paragraph("Mitigation State:", meta_label_style),
            Paragraph(f"<font color='{status_color.hexval()}'><b>{status_text}</b></font>", meta_val_style),
            Paragraph("Calculated Risk Score:", meta_label_style),
            Paragraph(f"<b>{risk_score}/100</b>", meta_val_style)
        ]
    ]
    
    summary_table = Table(summary_data, colWidths=[110, 160, 130, 140])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, BORDER_COLOR),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    
    # ── 1. Detection Stage (Agent 1 - Predict) ────────────────────────────────
    story.append(Paragraph("1. PIPELINE DETECTION (ANOMALY DETECTOR)", h1_style))
    
    if anomaly_score is not None:
        anom_txt = "ANOMALOUS BEHAVIOR DETECTED" if is_anomalous else "NORMAL SYSTEM BEHAVIOR"
        anom_color = DANGER_RED if is_anomalous else SUCCESS_GREEN
        
        predict_data = [
            [Paragraph("Decision Score:", meta_label_style), Paragraph(f"{anomaly_score:.4f}", meta_val_style)],
            [Paragraph("Pipeline Verdict:", meta_label_style), Paragraph(f"<font color='{anom_color.hexval()}'><b>{anom_txt}</b></font>", meta_val_style)]
        ]
        
        if reason_codes:
            codes_formatted = "<br/>".join([f"• {rc}" for rc in reason_codes])
            predict_data.append([Paragraph("Deviation Factors:", meta_label_style), Paragraph(codes_formatted, mono_style)])
            
        predict_table = Table(predict_data, colWidths=[130, 410])
        predict_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#f1f5f9")),
        ]))
        story.append(predict_table)
    else:
        story.append(Paragraph("No prediction records captured.", body_style))
        
    # ── 2. Threat Analysis Stage (Agent 2 - Investigate / RAG) ────────────────
    story.append(Paragraph("2. INTELLIGENT REASONING (MITRE ATT&CK & RAG MAP)", h1_style))
    
    if mitre_techniques:
        tech_list = []
        for t in mitre_techniques:
            tech_list.append(f"<b>{t.get('id', 'N/A')}</b>: {t.get('name', 'N/A')} (Confidence: {int(t.get('confidence', 0)*100)}%)")
        
        techs_formatted = "<br/>".join(tech_list)
        
        investigate_data = [
            [Paragraph("MITRE Mapping:", meta_label_style), Paragraph(techs_formatted, meta_val_style)],
            [Paragraph("Attack Confidence:", meta_label_style), Paragraph(f"<b>{int(attack_confidence * 100)}%</b>", meta_val_style)],
            [Paragraph("Predicted Next Stage:", meta_label_style), Paragraph(f"<b>{predicted_next_stage}</b>", meta_val_style)],
            [Paragraph("RAG Threat Explanation:", meta_label_style), Paragraph(explanation, body_style)]
        ]
        
        investigate_table = Table(investigate_data, colWidths=[130, 410])
        investigate_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#f1f5f9")),
        ]))
        story.append(investigate_table)
    else:
        story.append(Paragraph("No MITRE ATT&CK reasoning performed or required for this normal flow.", body_style))

    # ── 3. Mitigation & Audit History ─────────────────────────────────────────
    story.append(Paragraph("3. MITIGATION HISTORY & CONTROL AUDIT", h1_style))
    
    audit_rows = []
    
    if recommended_actions:
        actions_txt = ", ".join([f"<code>{a}</code>" for a in recommended_actions])
        audit_rows.append([Paragraph("Containment Plan:", meta_label_style), Paragraph(actions_txt, meta_val_style)])
    else:
        audit_rows.append([Paragraph("Containment Plan:", meta_label_style), Paragraph("None (Verdicts below mitigation threshold)", meta_val_style)])
        
    audit_rows.append([Paragraph("Manual Review Gate:", meta_label_style), Paragraph("Required" if approval_required else "Bypassed (Auto-approved)", meta_val_style)])
    
    if approval_required:
        dec_txt = "PENDING OPERATOR SIGN-OFF"
        dec_color = WARNING_AMBER
        if approval_state == "executed":
            dec_txt = f"APPROVED by <b>{approver}</b>"
            dec_color = SUCCESS_GREEN
        elif approval_state == "rejected":
            dec_txt = f"DENIED/REJECTED by <b>{approver}</b>"
            dec_color = DANGER_RED
            
        audit_rows.append([Paragraph("Review Decision:", meta_label_style), Paragraph(f"<font color='{dec_color.hexval()}'>{dec_txt}</font>", meta_val_style)])
        
        if executed_at:
            exec_time = datetime.fromisoformat(executed_at.replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M:%S') + " UTC"
            audit_rows.append([Paragraph("Execution Timestamp:", meta_label_style), Paragraph(exec_time, meta_val_style)])
    else:
        audit_rows.append([Paragraph("Review Decision:", meta_label_style), Paragraph("<font color='#16a34a'><b>AUTO-EXECUTED</b></font> (Monitor tier baseline)", meta_val_style)])
        
    audit_table = Table(audit_rows, colWidths=[130, 410])
    audit_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#f1f5f9")),
    ]))
    story.append(audit_table)
    
    # ── Footer Page Numbers ───────────────────────────────────────────────────
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(TEXT_MUTED)
        canvas.drawString(36, 20, "CONFIDENTIAL — SentinelX AI Security Operations Center")
        canvas.drawRightString(letter[0]-36, 20, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=incident_report_{record_id}.pdf"}
    )
