from sqlalchemy import Column, Integer, String, Text, DECIMAL, Date
from utils.database import Base, engine, Session
from config.database_bucket import TABLE_NAME


class DataTable(Base):
    """
    This is the database schema class
    """
    __tablename__ = TABLE_NAME
    Country_Name = Column(String(50), nullable=False)
    Company_Name = Column(String(50), nullable=False)
    Product_Name = Column(String(512), nullable=False)
    Product_URL = Column(String(512), primary_key=True, nullable=False)
    Image_URL = Column(String(512), nullable=False)
    Category = Column(String(50), nullable=False)
    Currency = Column(String(10))
    Price = Column(DECIMAL(precision=20, scale=3))
    Description = Column(Text)
    Product_Weight = Column(DECIMAL(precision=10, scale=3))
    Metal_Type = Column(String(50))
    Metal_Colour = Column(String(50))
    Metal_Purity = Column(Integer)
    Metal_Weight = Column(DECIMAL(precision=10, scale=3))
    Diamond_Colour = Column(String(100))
    Diamond_Clarity = Column(String(100))
    Diamond_Pieces = Column(Integer)
    Diamond_Weight = Column(DECIMAL(precision=10, scale=3))
    Flag = Column(String(10), nullable=False)
    Count = Column(Integer, default=0)
    Run_Date = Column(Date)

    def __repr__(self):
        """

        Returns: It returns a string representation of the object, in this case it will return a row from the database.

        """
        return f'Company_Name: {self.Company_Name}, Product_URL: {self.Product_URL}>'


# Below line will be executed when this module is imported while runtime. It creates a table using above schema if no table exists in the database.
Base.metadata.create_all(engine)
