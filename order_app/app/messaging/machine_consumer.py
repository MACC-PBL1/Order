# -*- coding: utf-8 -*-
"""Consumer that listens to Machine events and updates the Order database."""
import logging
from app.sql import crud, database, models
#from microservice_chassis.events import EventSubscriber
#from microservice_chassis.config import settings

logger = logging.getLogger(__name__)


class MachineEventConsumer:
    """Handles events from the Machine microservice."""
    
    def __init__(self):
        # Escuchar el exchange de Machine
        self.subscriber = EventSubscriber(
            exchange="factory.events",
            queue_name="order_machine_queue"
        )
        self._session_factory = database.SessionLocal
    
    async def start(self):
        """Start listening to Machine events."""
        logger.info("Order Service starting to listen for Machine events...")
        
        # Escuchar el evento de confirmación de Machine
        async for event in self.subscriber.listen("machine.confirmation_piece"):
            await self._handle_machine_event(event)
    
    async def _handle_machine_event(self, data: dict):
        """Process a machine event."""
        try:
            piece_id = data.get("piece_id")
            order_id = data.get("order_id")
            
            logger.info(f"Machine finished manufacturing piece {piece_id} from order {order_id}")
            
            async with self._session_factory() as db:
                # Actualizar estado de la pieza
                piece = await crud.update_piece_status(
                    db, piece_id, models.Piece.STATUS_MANUFACTURED
                )
                
                # Verificar si todas las piezas del pedido están terminadas
                order_id = piece.order_id
                result = await db.execute(
                    models.Piece.__table__.select()
                    .where(models.Piece.order_id == order_id)
                    .where(models.Piece.status != models.Piece.STATUS_MANUFACTURED)
                )
                remaining = result.scalars().all()
                
                if not remaining:
                    logger.info(f"All pieces manufactured! Marking order {order_id} as 'Completed'.")
                    await crud.update_order_status(
                        db, order_id, models.Order.STATUS_COMPLETED
                    )
        
        except Exception as e:
            logger.error(f"Error processing machine event: {e}", exc_info=True)