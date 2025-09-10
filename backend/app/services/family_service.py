from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.family import Family, FamilyMember, FamilyInvitation, FamilyRole
from app.models.user import User
from datetime import datetime, timedelta
from typing import Optional, List
import uuid

class FamilyService:
    @staticmethod
    def create_family(db: Session, name: str, created_by: str, currency: str = "USD") -> Family:
        """Create a new family and add the creator as admin."""
        family = Family(
            name=name,
            created_by=created_by,
            currency=currency,
            shared_budget=True
        )
        db.add(family)
        db.flush()  # Get the family ID
        
        # Add creator as admin member
        family_member = FamilyMember(
            family_id=family.id,
            user_id=created_by,
            role=FamilyRole.admin,
            is_active=True
        )
        db.add(family_member)
        db.commit()
        db.refresh(family)
        return family
    
    @staticmethod
    def get_user_families(db: Session, user_id: str) -> List[Family]:
        """Get all families where the user is a member."""
        return db.query(Family).join(FamilyMember).filter(
            and_(
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).all()
    
    @staticmethod
    def get_family_by_id(db: Session, family_id: str) -> Optional[Family]:
        """Get family by ID."""
        return db.query(Family).filter(Family.id == family_id).first()
    
    @staticmethod
    def get_family_members(db: Session, family_id: str) -> List[FamilyMember]:
        """Get all active members of a family."""
        return db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.is_active == True
            )
        ).all()
    
    @staticmethod
    def invite_member(db: Session, family_id: str, invited_phone: str, invited_by: str, 
                     role: FamilyRole = FamilyRole.member, message: Optional[str] = None) -> FamilyInvitation:
        """Create a family invitation."""
        # Check if inviter has admin role
        inviter_member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == invited_by,
                FamilyMember.role == FamilyRole.admin,
                FamilyMember.is_active == True
            )
        ).first()
        
        if not inviter_member:
            raise ValueError("Only family admins can invite new members")
        
        # Check if invitation already exists and is pending
        existing_invitation = db.query(FamilyInvitation).filter(
            and_(
                FamilyInvitation.family_id == family_id,
                FamilyInvitation.invited_phone == invited_phone,
                FamilyInvitation.is_accepted == False,
                FamilyInvitation.is_expired == False
            )
        ).first()
        
        if existing_invitation:
            raise ValueError("Una invitación pendiente ya existe para este número")
        
        # Create new invitation
        invitation = FamilyInvitation(
            family_id=family_id,
            invited_phone=invited_phone,
            invited_by=invited_by,
            role=role,
            message=message,
            expires_at=datetime.now() + timedelta(days=7)
        )
        
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation
    
    @staticmethod
    def accept_invitation(db: Session, invitation_id: str, user_id: str) -> FamilyMember:
        """Accept a family invitation."""
        invitation = db.query(FamilyInvitation).filter(
            FamilyInvitation.id == invitation_id
        ).first()
        
        if not invitation:
            raise ValueError("Invitación no encontrada")
        
        if invitation.is_accepted:
            raise ValueError("Esta invitación ya fue aceptada")
        
        if invitation.is_expired or datetime.now() > invitation.expires_at:
            raise ValueError("Esta invitación ha expirado")
        
        # Check if user is already a member
        existing_member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == invitation.family_id,
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).first()
        
        if existing_member:
            raise ValueError("Ya eres miembro de esta familia")
        
        # Create family member
        family_member = FamilyMember(
            family_id=invitation.family_id,
            user_id=user_id,
            role=invitation.role,
            is_active=True
        )
        
        # Mark invitation as accepted
        invitation.is_accepted = True
        invitation.accepted_at = datetime.now()
        
        db.add(family_member)
        db.commit()
        db.refresh(family_member)
        return family_member
    
    @staticmethod
    def get_pending_invitations_for_phone(db: Session, phone: str) -> List[FamilyInvitation]:
        """Get pending invitations for a phone number."""
        return db.query(FamilyInvitation).filter(
            and_(
                FamilyInvitation.invited_phone == phone,
                FamilyInvitation.is_accepted == False,
                FamilyInvitation.is_expired == False,
                FamilyInvitation.expires_at > datetime.now()
            )
        ).all()
    
    @staticmethod
    def remove_member(db: Session, family_id: str, user_id: str, removed_by: str):
        """Remove a member from the family."""
        # Check if remover has admin role
        remover_member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == removed_by,
                FamilyMember.role == FamilyRole.admin,
                FamilyMember.is_active == True
            )
        ).first()
        
        if not remover_member:
            raise ValueError("Solo los administradores pueden remover miembros")
        
        # Cannot remove yourself if you're the only admin
        if user_id == removed_by:
            admin_count = db.query(FamilyMember).filter(
                and_(
                    FamilyMember.family_id == family_id,
                    FamilyMember.role == FamilyRole.admin,
                    FamilyMember.is_active == True
                )
            ).count()
            
            if admin_count <= 1:
                raise ValueError("No puedes removerte siendo el único administrador")
        
        # Remove member
        member_to_remove = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).first()
        
        if not member_to_remove:
            raise ValueError("Miembro no encontrado")
        
        member_to_remove.is_active = False
        db.commit()
    
    @staticmethod
    def update_member_role(db: Session, family_id: str, user_id: str, new_role: FamilyRole, updated_by: str):
        """Update a member's role in the family."""
        # Check if updater has admin role
        updater_member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == updated_by,
                FamilyMember.role == FamilyRole.admin,
                FamilyMember.is_active == True
            )
        ).first()
        
        if not updater_member:
            raise ValueError("Solo los administradores pueden cambiar roles")
        
        # Cannot change your own role if you're the only admin
        if user_id == updated_by and new_role != FamilyRole.admin:
            admin_count = db.query(FamilyMember).filter(
                and_(
                    FamilyMember.family_id == family_id,
                    FamilyMember.role == FamilyRole.admin,
                    FamilyMember.is_active == True
                )
            ).count()
            
            if admin_count <= 1:
                raise ValueError("No puedes cambiar tu rol siendo el único administrador")
        
        # Update role
        member_to_update = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).first()
        
        if not member_to_update:
            raise ValueError("Miembro no encontrado")
        
        member_to_update.role = new_role
        db.commit()
        db.refresh(member_to_update)
        return member_to_update
    
    @staticmethod
    def is_family_member(db: Session, family_id: str, user_id: str) -> bool:
        """Check if user is an active member of the family."""
        member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).first()
        
        return member is not None
    
    @staticmethod
    def get_member_role(db: Session, family_id: str, user_id: str) -> Optional[FamilyRole]:
        """Get user's role in the family."""
        member = db.query(FamilyMember).filter(
            and_(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == user_id,
                FamilyMember.is_active == True
            )
        ).first()
        
        return member.role if member else None