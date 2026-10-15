"""How this pipeline identifies itself to the sources it reads.

Browser-compatible on purpose: USDA's portal answers 403 to a bare custom agent and 200 to the
conventional "Mozilla/5.0 (compatible; Name; +url)" form that crawlers use. It still names us.
"""
USER_AGENT = ("Mozilla/5.0 (compatible; ColoradoOpenFoodWeb/0.1; "
              "+https://github.com/open-food-web/colorado-open-food-web)")
