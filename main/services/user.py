# main/services/userService.py
from typing import Dict, Optional
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from main.repository.userRepository import UserRepository
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Servicio para lógica de negocio de usuarios"""

    def get_users_with_filters(self, search: Optional[str] = None,
                               status: Optional[str] = None,
                               role: Optional[str] = None,
                               order_by: str = '-date_joined') -> QuerySet:
        """Obtiene usuarios aplicando filtros"""
        # Usar directamente los métodos estáticos
        queryset = UserRepository.get_all(order_by)

        if search:
            queryset = UserRepository.filter_by_search(queryset, search)

        if status == 'active':
            queryset = UserRepository.filter_by_status(queryset, True)
        elif status == 'inactive':
            queryset = UserRepository.filter_by_status(queryset, False)

        if role:
            queryset = UserRepository.filter_by_role(queryset, role)

        return queryset

    def get_user_statistics(self) -> Dict[str, int]:
        """Obtiene estadísticas de usuarios"""
        return {
            'total_users': UserRepository.count_all(),
            'active_users': UserRepository.count_active(),
            'superusers': UserRepository.count_superusers(),
            'staff_users': UserRepository.count_staff(),
        }

    def get_user_by_id(self, user_id: int) -> User:
        """Obtiene un usuario por ID"""
        user = UserRepository.get_by_id(user_id)
        if not user:
            raise ValidationError(f'Usuario con ID {user_id} no existe')
        return user

    def get_user_data_dict(self, user: User) -> Dict:
        """Convierte un usuario a diccionario"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }

    def validate_password(self, password1: str, password2: str) -> None:
        """Valida contraseñas"""
        if password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')
        if len(password1) < 8:
            raise ValidationError('La contraseña debe tener al menos 8 caracteres.')

    def create_user(self, username: str, email: str, password1: str,
                    password2: str, first_name: str = '', last_name: str = '',
                    is_active: bool = True, is_staff: bool = False,
                    is_superuser: bool = False) -> User:
        """Crea un nuevo usuario con validaciones"""
        try:
            # Validaciones
            if UserRepository.exists_by_username(username):
                raise ValidationError(f'El usuario "{username}" ya existe.')

            if UserRepository.exists_by_email(email):
                raise ValidationError(f'El email "{email}" ya está registrado.')

            self.validate_password(password1, password2)

            # Crear usuario
            user = UserRepository.create(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                is_staff=is_staff,
                is_superuser=is_superuser
            )

            logger.info(f'Usuario creado exitosamente: {username}')
            return user

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f'Error al crear usuario: {str(e)}')
            raise ValidationError(f'Error al crear usuario: {str(e)}')

    def update_user(self, user_id: int, username: str, email: str,
                    first_name: str = '', last_name: str = '',
                    password: Optional[str] = None, is_active: bool = True,
                    is_staff: bool = False, is_superuser: bool = False) -> User:
        """Actualiza un usuario"""
        try:
            user = self.get_user_by_id(user_id)

            # Validaciones
            if UserRepository.exists_by_username(username, exclude_id=user_id):
                raise ValidationError(f'El usuario "{username}" ya existe.')

            if UserRepository.exists_by_email(email, exclude_id=user_id):
                raise ValidationError(f'El email "{email}" ya está registrado.')

            # Actualizar
            updated_user = UserRepository.update(
                user=user,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                is_active=is_active,
                is_staff=is_staff,
                is_superuser=is_superuser
            )

            logger.info(f'Usuario actualizado: {username}')
            return updated_user

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f'Error al actualizar usuario: {str(e)}')
            raise ValidationError(f'Error al actualizar usuario: {str(e)}')

    def delete_user(self, user_id: int, requesting_user_id: int) -> str:
        """Elimina un usuario"""
        try:
            if user_id == requesting_user_id:
                raise ValidationError('No puedes eliminar tu propia cuenta.')

            user = self.get_user_by_id(user_id)
            username = UserRepository.delete(user)

            logger.info(f'Usuario eliminado: {username}')
            return username

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f'Error al eliminar usuario: {str(e)}')
            raise ValidationError(f'Error al eliminar usuario: {str(e)}')