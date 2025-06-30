import React, { useState, useEffect } from "react";
import type { JSX } from "react";
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  BadgeCheck,
  BadgeX,
  BadgeMinus,
} from "lucide-react";

// Type definitions
interface Item {
  Description: string;
  Quantity: string;
  UnitPrice: string;
  Amount: string;
}

interface Flags {
  IncorrectVendorInfo?: boolean;
  DuplicateInvoice?: boolean;
  UnusualAmounts?: boolean;
  ItemizedInvoice?: boolean;
}

interface VendorInfo {
  vendorId?: string;
  VendorName: string;
  VendorEmail: string;
  VendorAddress: string;
  VendorGSTIN: string;
  VendorBankName: string;
  VendorBankAccount: string;
  VendorIFSCCode: string;
  VendorBankRoutingNumber: string;
}

interface Invoice {
  invoiceId: string;
  InvoiceNumber: string;
  InvoiceDate: string;
  DueDate: string;
  VendorEmail: string;
  TotalAmount: number;
  Currency: string;
  TaxAmount: number;
  Notes: string;
  TermsAndConditions: string;
  FileURL: string;
  Items: Item[];
  Flags?: Flags;
  VendorInfo?: VendorInfo;
}

interface VendorData {
  id: number;
  vendorInfo: VendorInfo;
}

interface ApiResponse {
  vendors: VendorInfo[];
  invoices: Invoice[];
}

interface ExpandedItems {
  [key: string]: boolean;
}

interface UnflaggingState {
  [key: string]: boolean;
}

type TabType = "unflagged" | "flagged" | "vendors";

interface Tab {
  id: TabType;
  label: string;
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("unflagged");
  const [expandedItems, setExpandedItems] = useState<ExpandedItems>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [unflagging, setUnflagging] = useState<UnflaggingState>({});

  // Data states
  const [allInvoices, setAllInvoices] = useState<Invoice[]>([]);
  const [vendors, setVendors] = useState<VendorInfo[]>([]);

  // Computed data based on flags
  const unflaggedData: Invoice[] = allInvoices.filter((invoice) => {
    const flags = invoice.Flags || {};
    return !Object.values(flags).some((flag) => flag === true);
  });

  const flaggedData: Invoice[] = allInvoices.filter((invoice) => {
    const flags = invoice.Flags || {};
    return Object.values(flags).some((flag) => flag === true);
  });

  const vendorsData: VendorData[] = vendors.map((vendor, index) => ({
    id: index + 1,
    vendorInfo: vendor,
  }));

  const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL;

  const toggleExpand = (tabType: TabType, itemId: string | number): void => {
    const key = `${tabType}-${itemId}`;
    setExpandedItems((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  // Fetch data from API
  const fetchData = async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(API_BASE_URL);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ApiResponse = await response.json();
      const { vendors: vendorsList, invoices: invoicesList } = data;
      invoicesList.forEach((invoice) => {
        try {
          // Parse items if they are in string format
          if (typeof invoice.Items === "string") {
            invoice.Items = JSON.parse(invoice.Items) as Item[];
          }
        } catch (error) {
          console.error(
            `Error parsing items for invoice ${invoice.invoiceId}:`,
            error
          );
          invoice.Items = [];
        }
        try {
          // Parse flags if they are in string format
          if (typeof invoice.Flags === "string") {
            invoice.Flags = JSON.parse(invoice.Flags) as Flags;
          }
        } catch (error) {
          console.error(
            `Error parsing flags for invoice ${invoice.invoiceId}:`,
            error
          );
          invoice.Flags = {};
        }
        try {
          // Parse vendor info if it is in string format
          if (typeof invoice.VendorInfo === "string") {
            invoice.VendorInfo = JSON.parse(invoice.VendorInfo) as VendorInfo;
          }
        } catch (error) {
          console.error(
            `Error parsing vendor info for invoice ${invoice.invoiceId}:`,
            error
          );
          invoice.VendorInfo = undefined;
        }
      });

      setAllInvoices(invoicesList || []);
      setVendors(vendorsList || []);
    } catch (err) {
      console.error("Error fetching data:", err);
      setError("Failed to fetch data. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Unflag invoice
  const unflagInvoice = async (invoice: Invoice): Promise<void> => {
    const invoiceId = invoice.invoiceId;
    setUnflagging((prev) => ({ ...prev, [invoiceId]: true }));

    try {
      // Send PUT request to unflag the invoice
      const unflagResponse = await fetch(`${API_BASE_URL}/${invoiceId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!unflagResponse.ok) {
        throw new Error(`Failed to unflag invoice: ${unflagResponse.status}`);
      }
      // If IncorrectVendorInfo flag is true, also add vendor info
      if (invoice.Flags?.IncorrectVendorInfo && invoice.VendorInfo) {
        try {
          const vendorResponse = await fetch(`${API_BASE_URL}/vendors/add`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(invoice.VendorInfo),
          });

          if (!vendorResponse.ok) {
            console.error("Failed to add vendor:", vendorResponse.status);
          }
        } catch (vendorError) {
          console.error("Error adding vendor:", vendorError);
          // Continue even if vendor addition fails
        }
      }

      // Refresh data after successful unflagging
      await fetchData();

      // Clear expanded state for this item
      setExpandedItems((prev) => {
        const newState = { ...prev };
        delete newState[`flagged-${invoice.invoiceId}`];
        return newState;
      });
    } catch (err) {
      console.error("Error unflagging invoice:", err);
      setError("Failed to unflag invoice. Please try again.");
    } finally {
      setUnflagging((prev) => ({ ...prev, [invoiceId]: false }));
    }
  };

  // Safe display function for null/undefined values
  const safeDisplay = (value: any): JSX.Element | string => {
    // Handle boolean values with badges
    if (typeof value === "boolean") {
      if (value === false) {
        return <BadgeCheck className='text-green-500' size={16} />;
      } else {
        return <BadgeX className='text-red-500' size={16} />;
      }
    }
    // console.log(value);
    if (value === null || value === undefined) {
      // Handle null/undefined values with badge
      return <BadgeMinus className='text-yellow-500' size={16} />;
    }

    // Handle empty string
    if (value === "") {
      return "-";
    }

    // Return string value for all other cases
    return String(value);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const tabs: Tab[] = [
    { id: "unflagged", label: "Unflagged Invoices" },
    { id: "flagged", label: "Flagged Invoices" },
    { id: "vendors", label: "Trusted Vendors" },
  ];

  const renderObjectDetails = (
    obj: Record<string, any> | undefined,
    title: string
  ): React.ReactElement | null => {
    if (!obj || typeof obj !== "object") return null;
    return (
      <div className='bg-gray-50 p-3 rounded-lg'>
        <h4 className='font-semibold text-gray-700 mb-2'>{title}</h4>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-2 text-sm'>
          {Object.entries(obj).map(([key, value]) => (
            <div key={key} className='flex '>
              <span className='text-gray-600'>{key}: &nbsp;</span>
              <span className='text-gray-800 font-medium'>
                {safeDisplay(value)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderContent = (): JSX.Element => {
    if (loading) {
      return (
        <div className='flex justify-center items-center py-12'>
          <div className='animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600'></div>
          <span className='ml-2 text-gray-600'>Loading...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className='bg-red-50 border border-red-200 rounded-lg p-4'>
          <div className='flex items-center'>
            <AlertTriangle className='h-5 w-5 text-red-400 mr-2' />
            <span className='text-red-800'>{error}</span>
          </div>
          <button
            onClick={fetchData}
            className='mt-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm'>
            Retry
          </button>
        </div>
      );
    }

    let currentData: Invoice[] | VendorData[];

    if (activeTab === "unflagged") {
      currentData = unflaggedData;
    } else if (activeTab === "flagged") {
      currentData = flaggedData;
    } else {
      currentData = vendorsData;
    }

    if (activeTab === "unflagged" || activeTab === "flagged") {
      const invoiceData = currentData as Invoice[];
      return (
        <div className='space-y-3'>
          {invoiceData.map((item) => {
            const isExpanded = expandedItems[`${activeTab}-${item.invoiceId}`];
            const isUnflagging = unflagging[item.invoiceId];

            return (
              <div
                key={item.invoiceId}
                className='bg-white rounded-lg border border-gray-200 hover:shadow-md transition-shadow'>
                <div
                  className='p-4 cursor-pointer flex justify-between items-center'
                  onClick={() => toggleExpand(activeTab, item.invoiceId)}>
                  <div className='flex items-center space-x-2'>
                    {isExpanded ? (
                      <ChevronDown size={20} />
                    ) : (
                      <ChevronRight size={20} />
                    )}
                    <div>
                      <h3 className='font-semibold text-gray-800'>
                        Invoice - {safeDisplay(item.invoiceId)}
                      </h3>
                      <p className='text-sm text-gray-600'>
                        By: {safeDisplay(item.VendorEmail)}
                      </p>
                    </div>
                  </div>
                  <div className='text-right'>
                    <p
                      className={`font-bold ${
                        activeTab === "flagged"
                          ? "text-red-600"
                          : "text-green-600"
                      }`}>
                      {item.Currency ? item.Currency : "$"}
                      {safeDisplay(item.TotalAmount)}
                    </p>
                    <span
                      className={`inline-block px-2 py-1 text-xs rounded-full ${
                        activeTab === "flagged"
                          ? "bg-red-100 text-red-800"
                          : "bg-green-100 text-green-800"
                      }`}>
                      {activeTab === "flagged" ? "Flagged" : "Approved"}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className='px-4 pb-4 border-t border-gray-100'>
                    <div className='grid grid-cols-1 md:grid-cols-2 gap-4 mt-4'>
                      <div className='space-y-3'>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Invoice Number:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.InvoiceNumber)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Invoice Date:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.InvoiceDate)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Due Date:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.DueDate)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Currency:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.Currency)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Tax Amount:
                          </label>
                          <p className='text-gray-800'>
                            {item.Currency ? item.Currency : "$"}
                            {safeDisplay(item.TaxAmount)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Notes:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.Notes)}
                          </p>
                        </div>
                      </div>

                      <div className='space-y-3'>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Terms & Conditions:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.TermsAndConditions)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            File URL:
                          </label>
                          {item.FileURL && item.FileURL !== "-" ? (
                            <a
                              href={item.FileURL}
                              className='text-blue-600 hover:underline text-sm break-all'>
                              {item.FileURL}
                            </a>
                          ) : (
                            <p className='text-gray-800'>-</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className='mt-4 space-y-3'>
                      <div>
                        <label className='text-sm font-medium text-gray-600 mb-2 block'>
                          Items:
                        </label>
                        <div className='bg-gray-50 p-3 rounded-lg'>
                          {item.Items && Array.isArray(item.Items) ? (
                            item.Items.map((subItem, index) => (
                              <div
                                key={index}
                                className='grid grid-cols-1 md:grid-cols-4 gap-2 text-sm py-2 border-b border-gray-200 last:border-b-0'>
                                <div>
                                  <span className='text-gray-600'>
                                    Description:
                                  </span>
                                  <span className='ml-2 text-gray-800'>
                                    {safeDisplay(subItem.Description)}
                                  </span>
                                </div>
                                <div>
                                  <span className='text-gray-600'>Qty:</span>
                                  <span className='ml-2 text-gray-800'>
                                    {safeDisplay(subItem.Quantity)}
                                  </span>
                                </div>
                                <div>
                                  <span className='text-gray-600'>Rate:</span>
                                  <span className='ml-2 text-gray-800'>
                                    {item.Currency ? item.Currency : "$"}
                                    {safeDisplay(subItem.UnitPrice)}
                                  </span>
                                </div>
                                <div>
                                  <span className='text-gray-600'>Amount:</span>
                                  <span className='ml-2 text-gray-800'>
                                    {item.Currency ? item.Currency : "$"}
                                    {safeDisplay(subItem.Amount)}
                                  </span>
                                </div>
                              </div>
                            ))
                          ) : (
                            <p className='text-gray-500 text-sm'>
                              No items available
                            </p>
                          )}
                        </div>
                      </div>

                      {renderObjectDetails(item.Flags, "Flags")}
                      {renderObjectDetails(
                        item.VendorInfo,
                        "Vendor Information"
                      )}

                      {/* Unflag button for flagged invoices */}
                      {activeTab === "flagged" && (
                        <div className='mt-4 pt-4 border-t border-gray-200'>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              unflagInvoice(item);
                            }}
                            disabled={isUnflagging}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                              isUnflagging
                                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                : "bg-green-600 text-white hover:bg-green-700"
                            }`}>
                            {isUnflagging ? "Unflagging..." : "Unflag Invoice"}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    if (activeTab === "vendors") {
      const vendorData = currentData as VendorData[];
      return (
        <div className='space-y-3'>
          {vendorData.map((item) => {
            const isExpanded = expandedItems[`${activeTab}-${item.id}`];
            return (
              <div
                key={item.id}
                className='bg-white rounded-lg border border-gray-200 hover:shadow-md transition-shadow'>
                <div
                  className='p-4 cursor-pointer flex justify-between items-center'
                  onClick={() => toggleExpand(activeTab, item.id)}>
                  <div className='flex items-center space-x-2'>
                    {isExpanded ? (
                      <ChevronDown size={20} />
                    ) : (
                      <ChevronRight size={20} />
                    )}
                    <div>
                      <h3 className='font-semibold text-gray-800'>
                        {safeDisplay(item.vendorInfo.VendorName)}
                      </h3>
                      <p className='text-sm text-gray-600'>
                        {safeDisplay(item.vendorInfo.VendorEmail)}
                      </p>
                    </div>
                  </div>
                  <div className='text-right'>
                    <span className='inline-block px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full'>
                      Active
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className='px-4 pb-4 border-t border-gray-100'>
                    <div className='grid grid-cols-1 md:grid-cols-2 gap-4 mt-4'>
                      <div className='space-y-3'>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Vendor ID:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.vendorId)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Vendor Name:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorName)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Email:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorEmail)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Address:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorAddress)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            GSTIN:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorGSTIN)}
                          </p>
                        </div>
                      </div>

                      <div className='space-y-3'>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Bank Name:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorBankName)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Bank Account:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorBankAccount)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            IFSC Code:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(item.vendorInfo.VendorIFSCCode)}
                          </p>
                        </div>
                        <div>
                          <label className='text-sm font-medium text-gray-600'>
                            Routing Number:
                          </label>
                          <p className='text-gray-800'>
                            {safeDisplay(
                              item.vendorInfo.VendorBankRoutingNumber
                            )}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    return <div>No content available</div>;
  };

  return (
    <div className='min-h-screen bg-gray-50 p-4'>
      <div className='max-w-4xl mx-auto'>
        {/* Header */}
        <div className='bg-white rounded-t-lg border border-gray-300 p-4 flex items-center justify-between'>
          <div className='text-2xl font-bold text-blue-600'>TrustBill</div>
          <div className='text-sm text-gray-600 font-medium'>Welcome</div>
        </div>

        {/* Main content area */}
        <div className='bg-white border-l border-r border-b border-gray-300 rounded-b-lg'>
          {/* Tab navigation */}
          <div className='border-b border-gray-200'>
            <nav className='flex space-x-8 px-6 py-4'>
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`pb-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? "border-blue-500 text-blue-600"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Content area */}
          <div className='p-6'>
            <div className='mb-4'>
              <h1 className='text-2xl font-bold text-gray-900 capitalize'>
                {activeTab} Items
              </h1>
              <p className='text-gray-600 text-sm mt-1'>
                {activeTab === "unflagged" &&
                  "Regular transactions awaiting processing"}
                {activeTab === "flagged" && "Transactions requiring attention"}
                {activeTab === "vendors" && "Vendor management and contacts"}
              </p>
            </div>

            {renderContent()}
          </div>

          {/* Footer */}
          <div className='border-t border-gray-200 px-6 py-4 bg-gray-50 rounded-b-lg'>
            <p className='text-sm text-gray-500'>
              Showing{" "}
              {activeTab === "unflagged"
                ? unflaggedData.length
                : activeTab === "flagged"
                ? flaggedData.length
                : vendorsData.length}{" "}
              {activeTab} items
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
