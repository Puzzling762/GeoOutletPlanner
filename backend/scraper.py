from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
import csv
import time

# Path to your Microsoft Edge WebDriver executable
driver_path = "C:/Users/raj37/Downloads/msedgedriver.exe"  # Update path as needed

# Configure Edge WebDriver options
options = Options()
options.add_argument("--headless")  # Run in headless mode (no browser UI)
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

# Initialize Edge WebDriver
driver = webdriver.Edge(service=Service(driver_path), options=options)

# Base URL of the webpage to scrape
base_url = "https://www.census2011.co.in/district.php?page="

# Initialize a list to store all the data
data = []

# Set the starting page number
page_number = 1

# Define a maximum number of pages to scrape (for safety, you can adjust this as needed)
max_pages = 100

while page_number <= max_pages:
    url = base_url + str(page_number)  # Generate the URL for the current page
    
    # Open the webpage
    driver.get(url)
    
    # Wait for the table to load (adjust the timeout as needed)
    time.sleep(3)  # Add a sleep time to ensure the page is fully loaded
    
    # Locate table rows
    rows = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
    
    if not rows:
        print(f"No rows found on page {page_number}. Breaking out of loop.")
        break  # Stop if no rows are found, indicating that we've reached the last page
    
    # Extract district and population
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) > 3:  # Ensure there are enough columns
            district = cols[1].text.strip()  # District name
            population_str = cols[3].text.strip()  # Population (as string)
            
            # Clean the population string: remove commas, extra spaces, and non-numeric characters
            cleaned_population_str = ''.join(filter(str.isdigit, population_str))
            
            # Try to convert to integer
            try:
                population = int(cleaned_population_str) if cleaned_population_str else 0
            except ValueError:
                population = 0  # If there's an issue with conversion, set population to 0
            
            data.append([district, population])

    print(f"Scraped data from page {page_number}")
    page_number += 1  # Move to the next page

# Write the data to a CSV file
csv_filename = "district_population_all_pages.csv"
with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["District", "Population"])  # Write header row
    writer.writerows(data)  # Write the data rows

# Close the browser
driver.quit()

print(f"Data successfully scraped and saved to {csv_filename}")
