"""
Utility functions for handling pension glossary terms and definitions
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Dictionary of pension terms and their definitions
# Imported from document_processor.py
PENSION_TERMS = {
    "PA16": "Pensionsavtal för statligt anställda från 2016",
    "PA03": "Pensionsavtal för statligt anställda från 2003",
    "ITP": "Industrins och handelns tilläggspension",
    "ITP1": "ITP-avdelning 1, premiebestämd ålderspension för födda 1979 eller senare",
    "ITP2": "ITP-avdelning 2, förmånsbestämd ålderspension för födda 1978 eller tidigare",
    "ITPK": "ITP kompletterande ålderspension",
    "KAP-KL": "Kollektivavtalad Pension för kommun- och landstingsanställda",
    "AKAP-KL": "Avgiftsbestämd Kollektivavtalad Pension för kommun- och landstingsanställda",
    "AKAP-KR": "Avgiftsbestämd Kollektivavtalad Pension för kommun- och regionsanställda",
    "SAP-R": "Särskild Avtalspension för Räddningstjänstpersonal",
    "SKR": "Sveriges Kommuner och Regioner",
    "SKR2023": "Pensionsavtal för kommuner och regioner från 2023",
    "PFA": "Pensions- och försäkringsavtal",
    "ATP": "Allmän tilläggspension",
    "PPM": "Premiepensionsmyndigheten",
    "SPV": "Statens tjänstepensionsverk",
    "KPA": "Kommunernas Pensionsanstalt",
    "AIP": "Avtalspension SAF-LO",
    "FTP": "Försäkringstjänstepension"
}

# Extended glossary with additional pension-related terms
EXTENDED_GLOSSARY = {
    **PENSION_TERMS,
    "pensionsålder": "Den ålder då en person normalt kan börja ta ut sin pension. I Sverige är den allmänna pensionsåldern 65 år, men det finns möjlighet att ta ut pension tidigare eller senare.",
    "tjänstepension": "Pension som betalas av arbetsgivaren enligt kollektivavtal eller individuellt avtal, som komplement till den allmänna pensionen.",
    "premiepension": "Del av den allmänna pensionen där individen själv kan välja hur pengarna ska placeras.",
    "inkomstpension": "Den största delen av den allmänna pensionen, baserad på livsinkomsten.",
    "förmånsbestämd pension": "Pension där förmånen (utbetalningen) är bestämd i förväg, ofta som en procentsats av slutlönen.",
    "avgiftsbestämd pension": "Pension där avgiften (insättningen) är bestämd, men förmånen beror på hur mycket som sätts in och hur pengarna förvaltas.",
    "pensionsgrundande inkomst": "Den inkomst som ligger till grund för beräkning av pensionsrätter.",
    "pensionsrätt": "Rätt till pension som tjänas in under arbetslivet.",
    "inkomstbasbelopp": "Ett belopp som används för att beräkna pensionsgrundande inkomst och andra förmåner. Justeras årligen.",
    "prisbasbelopp": "Ett belopp som används för att beräkna olika förmåner och avgifter. Justeras årligen baserat på prisutvecklingen.",
    "delningtal": "Faktor som används för att beräkna pensionsutbetalningar baserat på förväntad livslängd.",
    "kapitel": "En större avdelning i ett pensionsavtal som innehåller relaterade bestämmelser.",
    "paragraf": "En specifik bestämmelse eller regel i ett pensionsavtal, ofta markerad med §-symbol.",
    "avdelning": "En större sektion i ett pensionsavtal, som kan innehålla flera kapitel.",
    "bilaga": "Ett kompletterande dokument till huvudavtalet som innehåller ytterligare bestämmelser eller förtydliganden.",
    "ikraftträdande": "Datum då ett avtal eller en bestämmelse börjar gälla.",
    "övergångsbestämmelse": "Regler som gäller under en övergångsperiod när nya bestämmelser ersätter gamla.",
    "löneväxling": "Möjlighet att avstå en del av bruttolönen mot att arbetsgivaren istället betalar in motsvarande belopp till tjänstepensionen.",
    "efterlevandeskydd": "Skydd som innebär att efterlevande får ersättning om den försäkrade avlider.",
    "återbetalningsskydd": "Skydd som innebär att pensionskapitalet betalas ut till efterlevande om den försäkrade avlider.",
    "förvaltningsavgift": "Avgift som tas ut för förvaltning av pensionskapitalet.",
    "fondförsäkring": "Pensionsförsäkring där kapitalet placeras i fonder som den försäkrade själv väljer.",
    "traditionell försäkring": "Pensionsförsäkring där försäkringsbolaget ansvarar för placeringen av kapitalet och garanterar en viss minimiavkastning."
}

def is_glossary_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a query is asking for a definition of a term in the glossary.
    
    Args:
        query: The user query string
        
    Returns:
        Tuple of (is_glossary_query, matched_term)
    """
    # Normalize query
    query_lower = query.lower().strip()
    
    # Common patterns for glossary queries
    patterns = [
        r"vad är ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$",
        r"vad betyder ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$",
        r"vad innebär ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$",
        r"förklara ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$",
        r"definiera ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$",
        r"vad menas med ([a-zåäöA-ZÅÄÖ0-9-]+)(\?)?$"
    ]
    
    # Check each pattern
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            term = match.group(1).strip()
            # Check if the term exists in our glossary
            for glossary_term in EXTENDED_GLOSSARY:
                if term == glossary_term.lower():
                    logger.info(f"Matched glossary term: {glossary_term}")
                    return True, glossary_term
                
                # Also check for terms with spaces instead of hyphens
                if "-" in glossary_term:
                    space_variant = glossary_term.replace("-", " ").lower()
                    if term == space_variant:
                        logger.info(f"Matched glossary term (space variant): {glossary_term}")
                        return True, glossary_term
    
    # Special case for acronyms which might be in uppercase
    for term in EXTENDED_GLOSSARY:
        if term.upper() == query_lower or term.upper() + "?" == query_lower:
            logger.info(f"Matched glossary term (uppercase): {term}")
            return True, term
    
    return False, None

def get_glossary_response(term: str) -> str:
    """
    Get a formatted response for a glossary term.
    
    Args:
        term: The glossary term to look up
        
    Returns:
        A formatted response with the term definition
    """
    definition = EXTENDED_GLOSSARY.get(term)
    if not definition:
        logger.warning(f"Term '{term}' not found in glossary")
        return None
    
    # Format the response
    response = f"""## {term}

{definition}

Detta är en standarddefinition från pensionsordlistan. Om du vill ha mer detaljerad information om hur detta tillämpas i specifika pensionsavtal, vänligen ställ en mer specifik fråga."""

    logger.info(f"Generated glossary response for term: {term}")
    return response
