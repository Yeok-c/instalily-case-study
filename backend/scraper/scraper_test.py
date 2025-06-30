from seleniumbase import Driver

driver = Driver(uc=True)
driver.get("https://nowsecure.nl/#relax")
driver.save_screenshot("nowsecure.png")
driver.quit()