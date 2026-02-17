# orders/utils.py
import logging
import traceback
from django.db.models import Q
from products.models import Product

# ---------------- Helpers ----------------
logger = logging.getLogger(__name__)

def _get_product_by_identifier(identifier):
    """
    Robust lookup helper with verbose debug logging.
    Tries (in order):
      1. exact slug (case-sensitive)
      2. slug__iexact (case-insensitive)
      3. numeric id
      4. slug__icontains / name__icontains (broad search)
      5. handles "prefix-N" or "prefix_N" by trying prefix and numeric suffix heuristics

    Returns Product instance or None.
    **DEBUG INFO**: prints/logs every attempt so you can see why a lookup returned None.
    Remove the debug prints/logs when done.
    """
    logger.debug("[_get_product_by_identifier] START -> raw identifier: %r", identifier)
    print(f"[DEBUG] _get_product_by_identifier start: {identifier!r}")

    if identifier is None:
        logger.debug("[_get_product_by_identifier] identifier is None -> returning None")
        print("[DEBUG] identifier is None -> returning None")
        return None

    ident = str(identifier).strip()
    if not ident:
        logger.debug("[_get_product_by_identifier] identifier empty after strip -> returning None")
        print("[DEBUG] identifier empty after strip -> returning None")
        return None

    # 1) Try exact slug (case-sensitive)
    try:
        product = Product.objects.get(slug=ident)
        logger.debug("[_get_product_by_identifier] found by exact slug (case-sensitive): %s (id=%s)", product.slug, product.id)
        print("[DEBUG] Found by exact slug (case-sensitive):", product.id, product.slug)
        return product
    except Product.DoesNotExist:
        logger.debug("[_get_product_by_identifier] not found by exact slug (case-sensitive): %r", ident)
        print("[DEBUG] Not found by exact slug (case-sensitive).")
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception on exact slug lookup")
        print("[DEBUG] Exception during exact slug lookup:", e)
        traceback.print_exc()

    # 2) Try slug case-insensitive
    try:
        product = Product.objects.get(slug__iexact=ident)
        logger.debug("[_get_product_by_identifier] found by slug__iexact: %s (id=%s)", product.slug, product.id)
        print("[DEBUG] Found by slug__iexact:", product.id, product.slug)
        return product
    except Product.DoesNotExist:
        logger.debug("[_get_product_by_identifier] not found by slug__iexact: %r", ident)
        print("[DEBUG] Not found by slug__iexact.")
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception on slug__iexact")
        print("[DEBUG] Exception during slug__iexact lookup:", e)
        traceback.print_exc()

    # 3) Try numeric id
    try:
        pid = int(ident)
        try:
            product = Product.objects.get(id=pid)
            logger.debug("[_get_product_by_identifier] found by numeric id: %s", product.id)
            print("[DEBUG] Found by numeric id:", product.id)
            return product
        except Product.DoesNotExist:
            logger.debug("[_get_product_by_identifier] no product with id=%s", pid)
            print(f"[DEBUG] No product with id={pid}")
    except (ValueError, TypeError):
        logger.debug("[_get_product_by_identifier] identifier not an integer: %r", ident)
        print("[DEBUG] identifier not an integer:", ident)
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception converting identifier to int")
        print("[DEBUG] Exception converting identifier to int:", e)
        traceback.print_exc()

    # 4) Broad search: slug or name contains identifier (case-insensitive)
    try:
        candidates = Product.objects.filter(
            Q(slug__icontains=ident) | Q(name__icontains=ident)
        ).distinct()
        logger.debug("[_get_product_by_identifier] broad search candidates count: %d for ident=%r", candidates.count(), ident)
        print(f"[DEBUG] Broad search candidates count: {candidates.count()} for ident={ident!r}")
        if candidates.count() == 1:
            product = candidates.first()
            logger.debug("[_get_product_by_identifier] single broad candidate chosen id=%s slug=%s", product.id, product.slug)
            print("[DEBUG] Chosen single broad candidate:", product.id, product.slug)
            return product
        elif candidates.count() > 1:
            # Try to pick best candidate: slug exact-ish, or name exact-ish
            ident_lower = ident.lower()
            for cand in candidates:
                if cand.slug.lower() == ident_lower or (cand.name and cand.name.lower() == ident_lower):
                    logger.debug("[_get_product_by_identifier] picking candidate by exact match among many: id=%s", cand.id)
                    print("[DEBUG] Picking candidate by exact match among many:", cand.id)
                    return cand
            # fallback: choose first but log ambiguity
            product = candidates.first()
            logger.warning("[_get_product_by_identifier] multiple candidates found for %r - returning first id=%s slug=%s", ident, product.id, product.slug)
            print("[WARNING] multiple candidates found - returning first:", product.id, product.slug)
            return product
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception during broad search")
        print("[DEBUG] Exception during broad search:", e)
        traceback.print_exc()

    # 5) Heuristics for strings like "beverage-2" or "beverage_2"
    try:
        sep_candidates = ["-", "_", ":"]
        for sep in sep_candidates:
            if sep in ident:
                parts = ident.split(sep)
                prefix = parts[0].strip()
                suffix = parts[-1].strip()
                logger.debug("[_get_product_by_identifier] trying heuristic split by %r -> prefix=%r suffix=%r", sep, prefix, suffix)
                print(f"[DEBUG] Heuristic split by {sep}: prefix={prefix!r}, suffix={suffix!r}")

                # If suffix is numeric, try direct id
                try:
                    pid = int(suffix)
                    try:
                        product = Product.objects.get(id=pid)
                        logger.debug("[_get_product_by_identifier] heuristic found product by numeric suffix id=%s", pid)
                        print("[DEBUG] Heuristic found by numeric suffix id:", pid)
                        return product
                    except Product.DoesNotExist:
                        logger.debug("[_get_product_by_identifier] no product with heuristic id suffix=%s", pid)
                        print("[DEBUG] no product with heuristic id suffix:", pid)
                except (ValueError, TypeError):
                    logger.debug("[_get_product_by_identifier] suffix not integer, trying prefix search")
                    print("[DEBUG] suffix not integer; trying prefix search")

                # Try to find by prefix in slug/name
                candidate = Product.objects.filter(Q(slug__icontains=prefix) | Q(name__icontains=prefix)).first()
                if candidate:
                    logger.debug("[_get_product_by_identifier] heuristic picked candidate id=%s slug=%s", candidate.id, candidate.slug)
                    print("[DEBUG] Heuristic picked candidate:", candidate.id, candidate.slug)
                    return candidate
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception during heuristic step")
        print("[DEBUG] Exception during heuristic step:", e)
        traceback.print_exc()

    # Nothing matched
    logger.debug("[_get_product_by_identifier] NO MATCH for identifier=%r -> returning None", identifier)
    print("[DEBUG] NO MATCH for identifier:", identifier)
    return None
