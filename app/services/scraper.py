import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fastapi import HTTPException

class WebsiteScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/"
        }
        self.common_slugs = [
            "",
            "/faq",
            "/faqs",
            "/shipping",
            "/delivery",
            "/returns",
            "/return-policy",
            "/refund-policy",
            "/terms",
            "/terms-of-service",
            "/privacy",
            "/about",
            "/contact",
            "/collections/wardrobes",
            "/wardrobes"
        ]

    def _clean_html(self, html_text: str) -> str:
        soup = BeautifulSoup(html_text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        return soup.get_text(separator="\n", strip=True)

    async def scrape_domain(self, base_url: str) -> dict[str, str]:
        parsed_base = urlparse(base_url)
        domain_root = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        scraped_pages = {}
        visited_urls = set()
        wardrobe_collection_urls = set()
        max_wardrobe_products = 10
        wardrobe_product_count = 0

        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
            
            # 0. Force-fetch the exact base URL provided first
            try:
                exact_res = await client.get(base_url)
                if exact_res.status_code == 200:
                    page_text = self._clean_html(exact_res.text)
                    if len(page_text) > 100:
                        scraped_pages["homepage"] = page_text
                        visited_urls.add(base_url)
            except Exception as e:
                print(f"Warning: Failed to fetch exact URL {base_url}: {e}")

            # 1. Probe common slugs
            for slug in self.common_slugs:
                target_url = urljoin(domain_root, slug)
                if target_url in visited_urls:
                    continue
                visited_urls.add(target_url)

                try:
                    response = await client.get(target_url)
                    if response.status_code == 200:
                        page_text = self._clean_html(response.text)
                        if len(page_text) > 200:
                          page_key = slug.strip("/").replace("/", "-") or "homepage-slug"
                          if page_key not in scraped_pages:
                              scraped_pages[page_key] = page_text
                              
                          if "wardrobe" in slug.lower():
                              wardrobe_collection_urls.add(target_url)
                except Exception:
                    continue

            # 2. Crawl homepage links
            try:
                home_url = domain_root if domain_root not in visited_urls else list(visited_urls)[0]
                home_response = await client.get(home_url)
                if home_response.status_code == 200:
                    home_soup = BeautifulSoup(home_response.text, "html.parser")
                    for a_tag in home_soup.find_all("a", href=True):
                        full_url = urljoin(domain_root, a_tag["href"])
                        parsed_link = urlparse(full_url)
                        
                        if parsed_link.netloc != parsed_base.netloc:
                            continue
                            
                        path_lower = parsed_link.path.lower()
                        
                        if "wardrobe" in path_lower and "/products/" not in path_lower:
                            wardrobe_collection_urls.add(full_url)

                        if any(kw in path_lower for kw in ["policy", "shipping", "return", "faq", "terms", "help", "support", "delivery"]):
                            if full_url not in visited_urls:
                                visited_urls.add(full_url)
                                try:
                                    res = await client.get(full_url)
                                    if res.status_code == 200:
                                        link_text = self._clean_html(res.text)
                                        if len(link_text) > 200:
                                            slug_name = parsed_link.path.strip("/").replace("/", "-")
                                            scraped_pages[slug_name] = link_text
                                except Exception:
                                    continue
            except Exception:
                pass

            # 3. Crawl wardrobe products
            for collection_url in wardrobe_collection_urls:
                try:
                    col_res = await client.get(collection_url)
                    if col_res.status_code == 200:
                        col_soup = BeautifulSoup(col_res.text, "html.parser")
                        for a_tag in col_soup.find_all("a", href=True):
                            if wardrobe_product_count >= max_wardrobe_products:
                                break
                                
                            prod_url = urljoin(domain_root, a_tag["href"])
                            parsed_prod = urlparse(prod_url)
                            prod_path = parsed_prod.path.lower()

                            if (
                                parsed_prod.netloc == parsed_base.netloc
                                and prod_url not in visited_urls
                                and ("/products/" in prod_path or "wardrobe" in prod_path)
                            ):
                                visited_urls.add(prod_url)
                                try:
                                    p_res = await client.get(prod_url)
                                    if p_res.status_code == 200:
                                        prod_text = self._clean_html(p_res.text)
                                        if len(prod_text) > 200:
                                            slug_name = parsed_prod.path.strip("/").replace("/", "-")
                                            scraped_pages[slug_name] = prod_text
                                            wardrobe_product_count += 1
                                except Exception:
                                    continue
                except Exception:
                    continue

        if not scraped_pages:
            raise HTTPException(
                status_code=400, 
                detail=f"Could not retrieve any content from {base_url}. The site may be blocking automated requests or returning a non-200 status."
            )

        return scraped_pages