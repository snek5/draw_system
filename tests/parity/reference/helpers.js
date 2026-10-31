import seedrandom from "seedrandom";
import cryptoJs from "crypto-js";

const pickWinners = ({
    fileInput,
    perdanaWinners,
    nonPerdanaWinners,
    lineDelay,
    setRandomLine,
    setPickedLines,
    setFileHeaders,
    rngSeed,
    showName,
    showCertificate
}) => {
    if (!fileInput) {
        alert('Please choose a CSV file.');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const content = e.target.result;
        const lines = content.split('\n');
        const headers = lines[0].split('|').map((header) => header.trim());
        const data = lines.slice(1);

        setFileHeaders(headers);

        const rng = seedrandom(rngSeed);
        console.log(`RNG Seed Value used : `);

        const getRandomIndex = (max) => Math.floor(rng() * max);

        const perdanaIndex = headers.indexOf('PERDANA_FLAG');
        const chanceIndex = headers.indexOf('FINAL_CHANCES');
        const staffFlagIndex = headers.indexOf('STAFF_FLAG');

        if (perdanaIndex === -1) {
            alert('CSV file is missing the "PERDANA_FLAG" column.');
            return;
        }

        if (chanceIndex === -1) {
            alert('CSV file is missing the "FINAL_CHANCES" column.')
            return;
        }

        if (staffFlagIndex === -1) {
            alert('CSV file is missing the "STAFF_FLAG" column.')
            return;
        }

        let cumulativeSum = 0;
        const cumulativeChances = data.map((line) => {
            const lineData = line.split('|');
            if (lineData.length > chanceIndex && lineData[staffFlagIndex].trim() === 'N') {
                const chanceValue = parseFloat(lineData[chanceIndex].trim());
                if (!isNaN(chanceValue) && chanceValue >= 0) {
                    cumulativeSum += chanceValue;
                    return cumulativeSum;
                }
            }
            return 0;
        });

        const totalCumulativeSum = cumulativeSum;

        const randomLines = [];

        for (let i = 0; i < perdanaWinners; i++) {
            let randomIndex, randomLineData;
            const randomValue = rng() * totalCumulativeSum;
            randomIndex = cumulativeChances.findIndex(
                (cumulativeChances, index) => cumulativeChances >= randomValue && data[index].split('|')[perdanaIndex].trim() === 'Y' && data[index].split('|')[staffFlagIndex].trim() === 'N'
            );
            randomLineData = data[randomIndex].split('|');
            randomLines.push(data[randomIndex]);
            data.splice(randomIndex, 1); // Remove the picked line from the data array
            cumulativeSum -= parseFloat(randomLineData[chanceIndex].trim()); // Reduce the cumulative sum
            cumulativeChances.splice(randomIndex, 1); // Remove the picked line from the cumulativeChances array
        }

        for (let i = 0; i < nonPerdanaWinners; i++) {
            let randomIndex, randomLineData;
            const randomValue = rng() * cumulativeSum; // Use the updated cumulativeSum
            randomIndex = cumulativeChances.findIndex(
                (cumulativeChances, index) => cumulativeChances >= randomValue && data[index].split('|')[perdanaIndex].trim() === 'N' && data[index].split('|')[staffFlagIndex].trim() === 'N'
            );
            randomLineData = data[randomIndex].split('|');
            randomLines.push(data[randomIndex]);
            data.splice(randomIndex, 1); // Remove the picked line from the data array
            cumulativeSum -= parseFloat(randomLineData[chanceIndex].trim()); // Reduce the cumulative sum
            cumulativeChances.splice(randomIndex, 1); // Remove the picked line from the cumulativeChances array
        }

        randomLines.sort(() => rng() - 0.5);

        for (let i = 0; i < randomLines.length; i++) {
            setTimeout(() => {
                const randomLineData = randomLines[i].split('|');
                const name = randomLineData[headers.indexOf('ACNAME')].trim();
                const certificate = randomLineData[headers.indexOf('ACCTNO')].trim();
                
                randomLineData.push(`W${i + 1}: ${certificate}`);
                // choose to display cert, name or both.
                switch (showCertificate != null && showName != null) {
                  case (showCertificate && showName):
                    setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${name}\n${certificate}`]);
                    break;
                  case showCertificate:
                    setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${certificate}\n`]);
                    break;
                  case showName:
                    setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${name}\n`]);
                    break;
                  default:
                    setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${certificate}\n`]);
                    break;
                }
                setPickedLines((prevLines) => [...prevLines, randomLines[i]]);
            }, i * lineDelay * 1000);
        }        
        
        // downloadSelectedLines(fileHeaders, pickedLines)
    };

    reader.readAsText(fileInput);
};

const downloadSelectedLines = (fileHeaders, pickedLines, rngSeed, HashedValue) => {
    const finalLine = `RNG Seed = ${rngSeed} | File Hash = ${HashedValue}`
    const fileHeader = fileHeaders.join('|');
    const linesText = [fileHeader, ...pickedLines,finalLine].join('\n');
    const blob = new Blob([linesText], { type: 'text/plain' });

    const downloadLink = document.createElement("a");
    downloadLink.href = URL.createObjectURL(blob);
    downloadLink.download = "selected_lines.csv";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
};


const hashFile = (file, setHashedValue, setRngSeed) => {
  const fileReader = new FileReader();

  fileReader.onload = () => {
    const fileArrayBuffer = fileReader.result;
    const hashUint8Array = cryptoJs.SHA256(cryptoJs.lib.WordArray.create(fileArrayBuffer));
    const hashedValueHex = hashUint8Array.toString(cryptoJs.enc.Hex);

    // Generate a unique RNG seed for each file
    const randomBuffer = new Uint8Array(16);
    crypto.getRandomValues(randomBuffer);
    const rngSeed = Array.from(randomBuffer, (byte) => byte.toString(16)).join('');

    setHashedValue(hashedValueHex);
    setRngSeed(rngSeed);

    console.log(`RNG Seed: ${rngSeed}`);
    console.log(`Hashed File Value: ${hashedValueHex}`);
  };

  fileReader.readAsArrayBuffer(file);
};

const pickStaff = ({
    fileInput,
    staffWinners,
    lineDelay,
    setRandomLine,
    setPickedLines,
    setFileHeaders,
    rngSeed,
    showName,
    showCertificate
  }) => {
    if (!fileInput) {
      alert('Please choose a CSV file.');
      return;
    }
  
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result;
      const lines = content.split('\n');
      const headers = lines[0].split('|').map((header) => header.trim());
      const data = lines.slice(1);
  
      setFileHeaders(headers);
  
      const rng = seedrandom(rngSeed);
      console.log(`RNG Seed Value used : `);
  
      const getRandomIndex = (max) => Math.floor(rng() * max);
  
      const staffFlagIndex = headers.indexOf('STAFF_FLAG');
  
      if (staffFlagIndex === -1) {
        alert('CSV file is missing the "STAFF_FLAG" column.');
        return;
      }
  
      let cumulativeSum = 0;
      const cumulativeChances = data.map((line) => {
        const lineData = line.split('|');
        if (lineData.length > staffFlagIndex && lineData[staffFlagIndex].trim() === 'Y') {
          const chanceValue = 1; // Assuming each staff member has an equal chance (adjust if needed)
          cumulativeSum += chanceValue;
          return cumulativeSum;
        }
        return 0;
      });
  
      const totalCumulativeSum = cumulativeSum;
  
      const randomLines = [];
  
      for (let i = 0; i < staffWinners; i++) {
        let randomIndex, randomLineData;
        const randomValue = rng() * totalCumulativeSum;
        randomIndex = cumulativeChances.findIndex(
          (cumulativeChances, index) => cumulativeChances >= randomValue && data[index].split('|')[staffFlagIndex].trim() === 'Y'
        );
        randomLineData = data[randomIndex].split('|');
        randomLines.push(data[randomIndex]);
        data.splice(randomIndex, 1); // Remove the picked line from the data array
        cumulativeSum -= 1; // Assuming each staff member has an equal chance
        cumulativeChances.splice(randomIndex, 1); // Remove the picked line from the cumulativeChances array
      }
  
      randomLines.sort(() => rng() - 0.5);
  
      for (let i = 0; i < randomLines.length; i++) {
        setTimeout(() => {
          const randomLineData = randomLines[i].split('|');
          const name = randomLineData[headers.indexOf('ACNAME')].trim();
          const certificate = randomLineData[headers.indexOf('ACCTNO')].trim();
          
          randomLineData.push(`W${i + 1}: ${certificate}`);
          // choose to display cert, name or both.
          switch (showCertificate != null && showName != null) {
            case (showCertificate && showName):
              setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${name}\n${certificate}`]);
              break;
            case showCertificate:
              setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${certificate}\n`]);
              break;
            case showName:
              setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${name}\n`]);
              break;
            default:
              setRandomLine((prevRandomLines) => [...prevRandomLines, `W${i + 1}: ${name}\n`]);
              break;
          }
          setPickedLines((prevLines) => [...prevLines, randomLines[i]]);
        }, i * lineDelay * 1000);
      }
      
      // downloadSelectedLines(fileHeaders, pickedLines)
    };
  
    reader.readAsText(fileInput);
  };

export { pickWinners, pickStaff, downloadSelectedLines, hashFile };
