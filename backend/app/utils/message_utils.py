"""
Utilities for handling WhatsApp message formatting and length constraints.
"""

def split_message_for_whatsapp(message: str, max_length: int = 1400) -> list:
    """
    Split long messages into WhatsApp-compatible chunks.
    
    Args:
        message: The message to split
        max_length: Maximum length per message (default 1400 to stay under 1600 limit)
    
    Returns:
        List of message chunks
    """
    if len(message) <= max_length:
        return [message]
    
    # Split by paragraphs first (double newlines)
    paragraphs = message.split('\n\n')
    messages = []
    current_message = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit, start new message
        if len(current_message + paragraph + '\n\n') > max_length:
            if current_message:
                messages.append(current_message.strip())
                current_message = paragraph + '\n\n'
            else:
                # Paragraph itself is too long, split by sentences
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_message + sentence + '. ') > max_length:
                        if current_message:
                            messages.append(current_message.strip())
                            current_message = sentence + '. '
                        else:
                            # Sentence is too long, just truncate
                            messages.append(sentence[:max_length-3] + "...")
                            current_message = ""
                    else:
                        current_message += sentence + '. '
        else:
            current_message += paragraph + '\n\n'
    
    # Add remaining content
    if current_message.strip():
        messages.append(current_message.strip())
    
    # Add continuation indicators
    for i, msg in enumerate(messages):
        if i < len(messages) - 1:
            messages[i] = msg + "\n\n📄 *(continúa...)*"
        else:
            # Last message gets an indicator
            messages[i] = msg + "\n\n✅ *(fin)*"
    
    return messages

def format_response_with_split(response_text: str) -> dict:
    """
    Format a response for WhatsApp, splitting if necessary.
    
    Args:
        response_text: The response text to format
    
    Returns:
        Dict with 'message' and optionally 'additional_messages'
    """
    if len(response_text) > 1400:
        messages = split_message_for_whatsapp(response_text)
        return {
            "message": messages[0],
            "additional_messages": messages[1:] if len(messages) > 1 else []
        }
    else:
        return {
            "message": response_text,
            "additional_messages": []
        }

def create_whatsapp_response(success: bool, message: str, response_type: str = "general", **kwargs) -> dict:
    """
    Create a standardized WhatsApp response with automatic message splitting.
    
    Args:
        success: Whether the operation was successful
        message: The response message
        response_type: Type of response (for categorization)
        **kwargs: Additional fields to include in response
    
    Returns:
        Standardized response dict
    """
    formatted = format_response_with_split(message)
    
    response = {
        "success": success,
        "message": formatted["message"],
        "type": response_type,
        **kwargs
    }
    
    if formatted["additional_messages"]:
        response["additional_messages"] = formatted["additional_messages"]
    
    return response