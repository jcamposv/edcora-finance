from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.organization import Organization, OrganizationMember, OrganizationInvitation, OrganizationType, OrganizationRole
from app.models.user import User
from datetime import datetime, timedelta
from typing import Optional, List
import uuid

class OrganizationService:
    @staticmethod
    def create_organization(db: Session, name: str, created_by: str, organization_type: OrganizationType = OrganizationType.family, currency: str = "USD") -> Organization:
        """Create a new organization and add the creator as owner."""
        organization = Organization(
            name=name,
            type=organization_type,
            owner_id=created_by,
            currency=currency
        )
        db.add(organization)
        db.flush()  # Get the organization ID
        
        # Add creator as owner member
        organization_member = OrganizationMember(
            organization_id=organization.id,
            user_id=created_by,
            role=OrganizationRole.owner,
            is_active=True
        )
        db.add(organization_member)
        db.commit()
        db.refresh(organization)
        return organization
    
    @staticmethod
    def get_user_organizations(db: Session, user_id: str) -> List[Organization]:
        """Get all organizations where the user is a member."""
        return db.query(Organization).join(OrganizationMember).filter(
            and_(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                Organization.is_active == True
            )
        ).all()
    
    @staticmethod
    def get_organization_by_id(db: Session, organization_id: str) -> Optional[Organization]:
        """Get organization by ID."""
        return db.query(Organization).filter(Organization.id == organization_id).first()
    
    @staticmethod
    def get_organization_members(db: Session, organization_id: str) -> List[OrganizationMember]:
        """Get all active members of an organization."""
        return db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.is_active == True
            )
        ).all()
    
    @staticmethod
    def invite_member(db: Session, organization_id: str, invited_phone: str, invited_by: str, 
                     role: OrganizationRole = OrganizationRole.member, message: Optional[str] = None) -> OrganizationInvitation:
        """Create an organization invitation."""
        # Check if inviter has admin+ role
        inviter_member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == invited_by,
                OrganizationMember.role.in_([OrganizationRole.owner, OrganizationRole.admin]),
                OrganizationMember.is_active == True
            )
        ).first()
        
        if not inviter_member:
            raise ValueError("Only organization owners and admins can invite new members")
        
        # Check if invitation already exists and is pending
        existing_invitation = db.query(OrganizationInvitation).filter(
            and_(
                OrganizationInvitation.organization_id == organization_id,
                OrganizationInvitation.invited_phone == invited_phone,
                OrganizationInvitation.accepted_at == None,
                OrganizationInvitation.is_active == True
            )
        ).first()
        
        if existing_invitation:
            raise ValueError("Una invitación pendiente ya existe para este número")
        
        # Create new invitation
        invitation = OrganizationInvitation(
            organization_id=organization_id,
            invited_phone=invited_phone,
            invited_by=invited_by,
            role=role.value,  # Store as string
            message=message
        )
        
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation
    
    @staticmethod
    def accept_invitation(db: Session, invitation_id: str, user_id: str) -> OrganizationMember:
        """Accept an organization invitation."""
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.id == invitation_id
        ).first()
        
        if not invitation:
            raise ValueError("Invitación no encontrada")
        
        if invitation.accepted_at:
            raise ValueError("Esta invitación ya fue aceptada")
        
        if not invitation.is_active:
            raise ValueError("Esta invitación ha expirado")
        
        # Check if user is already a member
        existing_member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == invitation.organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()
        
        if existing_member:
            raise ValueError("Ya eres miembro de esta organización")
        
        # Create organization member
        organization_member = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=user_id,
            role=OrganizationRole(invitation.role),
            is_active=True
        )
        
        # Mark invitation as accepted
        invitation.accepted_at = datetime.now()
        invitation.accepted_by = user_id
        
        db.add(organization_member)
        db.commit()
        db.refresh(organization_member)
        return organization_member
    
    @staticmethod
    def get_pending_invitations_for_phone(db: Session, phone: str) -> List[OrganizationInvitation]:
        """Get pending invitations for a phone number."""
        return db.query(OrganizationInvitation).filter(
            and_(
                OrganizationInvitation.invited_phone == phone,
                OrganizationInvitation.accepted_at == None,
                OrganizationInvitation.is_active == True
            )
        ).all()
    
    @staticmethod
    def remove_member(db: Session, organization_id: str, user_id: str, removed_by: str):
        """Remove a member from the organization."""
        # Check if remover has admin+ role
        remover_member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == removed_by,
                OrganizationMember.role.in_([OrganizationRole.owner, OrganizationRole.admin]),
                OrganizationMember.is_active == True
            )
        ).first()
        
        if not remover_member:
            raise ValueError("Solo los propietarios y administradores pueden remover miembros")
        
        # Cannot remove yourself if you're the only owner
        if user_id == removed_by:
            owner_count = db.query(OrganizationMember).filter(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.role == OrganizationRole.owner,
                    OrganizationMember.is_active == True
                )
            ).count()
            
            if owner_count <= 1:
                raise ValueError("No puedes removerte siendo el único propietario")
        
        # Remove member
        member_to_remove = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()
        
        if not member_to_remove:
            raise ValueError("Miembro no encontrado")
        
        member_to_remove.is_active = False
        db.commit()
    
    @staticmethod
    def update_member_role(db: Session, organization_id: str, user_id: str, new_role: OrganizationRole, updated_by: str):
        """Update a member's role in the organization."""
        # Check if updater has admin+ role
        updater_member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == updated_by,
                OrganizationMember.role.in_([OrganizationRole.owner, OrganizationRole.admin]),
                OrganizationMember.is_active == True
            )
        ).first()
        
        if not updater_member:
            raise ValueError("Solo los propietarios y administradores pueden cambiar roles")
        
        # Cannot change your own role if you're the only owner
        if user_id == updated_by and new_role != OrganizationRole.owner:
            owner_count = db.query(OrganizationMember).filter(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.role == OrganizationRole.owner,
                    OrganizationMember.is_active == True
                )
            ).count()
            
            if owner_count <= 1:
                raise ValueError("No puedes cambiar tu rol siendo el único propietario")
        
        # Update role
        member_to_update = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()
        
        if not member_to_update:
            raise ValueError("Miembro no encontrado")
        
        member_to_update.role = new_role
        db.commit()
        db.refresh(member_to_update)
        return member_to_update
    
    @staticmethod
    def is_organization_member(db: Session, organization_id: str, user_id: str) -> bool:
        """Check if user is an active member of the organization."""
        member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()
        
        return member is not None
    
    @staticmethod
    def get_member_role(db: Session, organization_id: str, user_id: str) -> Optional[OrganizationRole]:
        """Get user's role in the organization."""
        member = db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()
        
        return member.role if member else None
    
    @staticmethod
    def get_user_membership(db: Session, user_id: str, organization_id: str) -> Optional[OrganizationMember]:
        """Get user's membership details in the organization."""
        return db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True
            )
        ).first()